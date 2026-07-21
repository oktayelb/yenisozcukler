import contextvars
import functools
import inspect
import json
import logging
import time
import uuid

from django.conf import settings
from django.db import DatabaseError
from django.http.request import RawPostDataException
from django.utils import timezone

logger = logging.getLogger(__name__)

_current_request = contextvars.ContextVar('audit_current_request', default=None)
_current_request_log = contextvars.ContextVar('audit_current_request_log', default=None)

DEFAULT_SENSITIVE_KEYS = {
    'authorization',
    'cf_turnstile_response',
    'cookie',
    'csrfmiddlewaretoken',
    'new_password',
    'password',
    'secret',
    'sessionid',
    'token',
}


def audit_enabled():
    return getattr(settings, 'AUDIT_LOG_ENABLED', True)


def bind_audit_context(request, request_log):
    request_token = _current_request.set(request)
    request_log_token = _current_request_log.set(request_log)
    return request_token, request_log_token


def reset_audit_context(tokens):
    request_token, request_log_token = tokens
    _current_request.reset(request_token)
    _current_request_log.reset(request_log_token)


def get_current_request():
    return _current_request.get()


def get_current_request_log():
    return _current_request_log.get()


def attach_audit_metadata(request=None, **metadata):
    request = _normalize_request(request) or get_current_request()
    if request is None:
        return

    existing = getattr(request, '_audit_extra_metadata', {})
    existing.update(sanitize_value(metadata))
    request._audit_extra_metadata = existing


def get_client_ip(request):
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR') or None


def should_log_request(request):
    if not audit_enabled():
        return False

    excluded_prefixes = getattr(settings, 'AUDIT_LOG_EXCLUDE_PATH_PREFIXES', ())
    path = getattr(request, 'path', '')
    return not any(prefix and path.startswith(prefix) for prefix in excluded_prefixes)


def start_request_log(request, request_id, started_at):
    from .models import RequestLog

    try:
        return RequestLog.objects.create(
            request_id=request_id,
            method=request.method[:12],
            path=request.path[:2048],
            query_params=sanitize_querydict(request.GET),
            request_data=get_request_data(request),
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referer=request.META.get('HTTP_REFERER', ''),
            started_at=started_at,
        )
    except DatabaseError as exc:
        logger.warning('Could not create request audit log: %s', exc)
        return None


def finish_request_log(request_log, request, response, duration_ms, exc=None):
    if request_log is None:
        return

    user, username_snapshot, is_authenticated = resolve_actor(request)
    route_name = getattr(request, '_audit_route_name', '') or ''
    view_name = getattr(request, '_audit_view_name', '') or ''

    request_log.user = user if is_authenticated else None
    request_log.username_snapshot = username_snapshot
    request_log.is_authenticated = is_authenticated
    request_log.session_key = get_session_key(request)
    request_log.route_name = route_name[:150]
    request_log.view_name = view_name[:255]
    request_log.status_code = get_status_code(response, exc)
    request_log.response_bytes = get_response_bytes(response)
    request_log.duration_ms = duration_ms
    request_log.finished_at = timezone.now()

    if exc is not None:
        request_log.error_type = exc.__class__.__name__[:255]
        request_log.error_message = str(exc)

    try:
        request_log.save(update_fields=[
            'user',
            'username_snapshot',
            'is_authenticated',
            'session_key',
            'route_name',
            'view_name',
            'status_code',
            'response_bytes',
            'duration_ms',
            'finished_at',
            'error_type',
            'error_message',
        ])
    except DatabaseError as save_exc:
        logger.warning('Could not finish request audit log: %s', save_exc)


def describe_view(request, view_func, view_args=None, view_kwargs=None):
    view_args = view_args or ()
    view_kwargs = view_kwargs or {}
    resolver_match = getattr(request, 'resolver_match', None)
    route_name = getattr(resolver_match, 'url_name', '') if resolver_match else ''

    original_func = inspect.unwrap(view_func)
    module = getattr(original_func, '__module__', '') or ''
    function_name = getattr(original_func, '__name__', '') or view_func.__class__.__name__
    view_name = f'{module}.{function_name}' if module else function_name

    view_class = getattr(view_func, 'view_class', None) or getattr(view_func, 'cls', None)
    actions = getattr(view_func, 'actions', None) or {}
    action = actions.get(request.method.lower())
    resolver_func_path = getattr(resolver_match, '_func_path', '') if resolver_match else ''

    if view_class:
        module = getattr(view_class, '__module__', '') or module
        class_name = getattr(view_class, '__name__', view_class.__class__.__name__)
        resolved_leaf = resolver_func_path.rsplit('.', 1)[-1] if resolver_func_path else ''
        if action:
            function_name = f'{class_name}.{action}'
            view_name = f'{module}.{function_name}' if module else function_name
        elif resolved_leaf and resolved_leaf == class_name:
            function_name = class_name
            view_name = resolver_func_path
        else:
            function_name = f'{class_name}.dispatch'
            view_name = f'{module}.{function_name}' if module else function_name
    elif resolver_func_path:
        module, _, function_name = resolver_func_path.rpartition('.')
        view_name = resolver_func_path

    return {
        'module': module[:255],
        'function_name': function_name[:255],
        'route_name': (route_name or '')[:150],
        'view_name': view_name[:255],
        'view_args': sanitize_value(list(view_args)),
        'view_kwargs': sanitize_value(view_kwargs),
        'drf_action': action or '',
    }


def record_view_call(request, request_log, duration_ms, exc=None):
    view_info = getattr(request, '_audit_view_info', None)
    if not view_info:
        return

    metadata = {
        'kind': 'view',
        'route_name': view_info.get('route_name', ''),
        'view_name': view_info.get('view_name', ''),
        'view_args': view_info.get('view_args', []),
        'view_kwargs': view_info.get('view_kwargs', {}),
    }
    if view_info.get('drf_action'):
        metadata['drf_action'] = view_info['drf_action']
    metadata.update(getattr(request, '_audit_extra_metadata', {}))

    record_function_call(
        function_name=view_info.get('function_name') or view_info.get('view_name') or 'unknown_view',
        module=view_info.get('module', ''),
        label='view',
        request=request,
        request_log=request_log,
        duration_ms=duration_ms,
        metadata=metadata,
        exc=exc,
    )


def record_function_call(
    function_name,
    module='',
    label='',
    request=None,
    request_log=None,
    duration_ms=None,
    arguments=None,
    metadata=None,
    exc=None,
    started_at=None,
):
    if not audit_enabled():
        return

    from .models import FunctionCallLog

    request = _normalize_request(request) or get_current_request()
    request_log = request_log if request_log is not None else get_current_request_log()
    user, username_snapshot, is_authenticated = resolve_actor(request)
    started_at = started_at or timezone.now()
    status = FunctionCallLog.STATUS_ERROR if exc else FunctionCallLog.STATUS_SUCCESS

    try:
        FunctionCallLog.objects.create(
            request_log=request_log,
            request_id=getattr(request_log, 'request_id', getattr(request, '_audit_request_id', None)),
            user=user if is_authenticated else None,
            username_snapshot=username_snapshot,
            is_authenticated=is_authenticated,
            session_key=get_session_key(request),
            ip_address=get_client_ip(request) if request is not None else None,
            module=(module or '')[:255],
            function_name=(function_name or 'unknown')[:255],
            label=(label or '')[:255],
            arguments=sanitize_value(arguments or {}),
            metadata=sanitize_value(metadata or {}),
            status=status,
            duration_ms=duration_ms,
            error_type=exc.__class__.__name__[:255] if exc else '',
            error_message=str(exc) if exc else '',
            started_at=started_at,
            finished_at=timezone.now(),
        )
    except DatabaseError as db_exc:
        logger.warning('Could not create function audit log: %s', db_exc)


def log_function_call(label='', capture_args=False, metadata=None, metadata_getter=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not audit_enabled():
                return func(*args, **kwargs)

            started_perf = time.perf_counter()
            started_at = timezone.now()
            exc = None
            try:
                return func(*args, **kwargs)
            except Exception as caught:
                exc = caught
                raise
            finally:
                duration_ms = elapsed_ms(started_perf)
                call_metadata = metadata.copy() if isinstance(metadata, dict) else {}
                if metadata_getter is not None:
                    try:
                        call_metadata.update(metadata_getter(*args, **kwargs) or {})
                    except Exception as metadata_exc:
                        call_metadata['_metadata_error'] = str(metadata_exc)

                arguments = {}
                if capture_args:
                    arguments = {
                        'args': list(args),
                        'kwargs': kwargs,
                    }

                record_function_call(
                    function_name=func.__qualname__,
                    module=func.__module__,
                    label=label,
                    request=find_request(args, kwargs),
                    duration_ms=duration_ms,
                    arguments=arguments,
                    metadata=call_metadata,
                    exc=exc,
                    started_at=started_at,
                )

        return wrapper

    return decorator


class AuditContextMixin:
    """Optional DRF mixin for adding viewset action metadata to request logs."""

    def initial(self, request, *args, **kwargs):
        attach_audit_metadata(
            request,
            drf_action=getattr(self, 'action', ''),
            drf_basename=getattr(self, 'basename', ''),
            drf_detail=getattr(self, 'detail', None),
            drf_viewset=self.__class__.__name__,
        )
        return super().initial(request, *args, **kwargs)


def elapsed_ms(started_perf):
    return max(0, int((time.perf_counter() - started_perf) * 1000))


def get_status_code(response, exc=None):
    if response is not None:
        return getattr(response, 'status_code', None)
    if exc is not None:
        return 500
    return None


def get_response_bytes(response):
    if response is None:
        return None

    header_value = None
    if hasattr(response, 'get'):
        header_value = response.get('Content-Length')
    if header_value:
        try:
            return int(header_value)
        except (TypeError, ValueError):
            pass

    if hasattr(response, 'content'):
        try:
            return len(response.content)
        except Exception:
            return None

    return None


def get_request_data(request):
    if not getattr(settings, 'AUDIT_LOG_CAPTURE_REQUEST_DATA', True):
        return {}

    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return {}

    content_type = (request.META.get('CONTENT_TYPE') or '').split(';')[0].strip().lower()
    content_length = _safe_int(request.META.get('CONTENT_LENGTH'))
    max_body_bytes = getattr(settings, 'AUDIT_LOG_MAX_BODY_BYTES', 8192)
    if content_length and content_length > max_body_bytes:
        return {
            '_skipped': 'body_too_large',
            'content_length': content_length,
            'max_body_bytes': max_body_bytes,
        }

    if content_type == 'application/json':
        try:
            body = request.body
        except (RawPostDataException, OSError):
            return {'_skipped': 'body_unavailable'}
        if not body:
            return {}
        try:
            payload = json.loads(body.decode(request.encoding or 'utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {'_skipped': 'invalid_json_body'}
        return sanitize_value(payload)

    if content_type == 'application/x-www-form-urlencoded':
        return sanitize_querydict(request.POST)

    if content_type:
        return {'_skipped': f'unsupported_content_type:{content_type}'}

    return {}


def sanitize_querydict(querydict):
    return sanitize_value({
        key: values if len(values) > 1 else values[0]
        for key, values in querydict.lists()
    })


def sanitize_value(value, key=None, depth=0):
    if _is_sensitive_key(key):
        return '[redacted]'
    if depth > 5:
        return '[max_depth]'

    if isinstance(value, dict):
        return {
            str(item_key)[:120]: sanitize_value(item_value, key=item_key, depth=depth + 1)
            for item_key, item_value in list(value.items())[:50]
        }

    if isinstance(value, (list, tuple, set)):
        return [sanitize_value(item, depth=depth + 1) for item in list(value)[:50]]

    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str):
            return _truncate(value)
        return value

    if isinstance(value, uuid.UUID):
        return str(value)

    pk = getattr(value, 'pk', None)
    meta = getattr(value, '_meta', None)
    if meta is not None:
        return {
            'model': f'{meta.app_label}.{meta.model_name}',
            'pk': pk,
        }

    return _truncate(repr(value), limit=240)


def resolve_actor(request):
    if request is None:
        return None, '', False

    user = getattr(request, 'user', None)
    if _is_authenticated_user(user):
        return user, _username(user), True

    initial_user = getattr(request, '_audit_user_at_view', None)
    if _is_authenticated_user(initial_user):
        return initial_user, _username(initial_user), True

    return None, '', False


def get_session_key(request):
    if request is None:
        return ''

    session = getattr(request, 'session', None)
    if session is not None and getattr(session, 'session_key', None):
        return session.session_key or ''

    return getattr(request, '_audit_session_key_at_view', '') or ''


def remember_actor_at_view(request):
    request._audit_user_at_view = getattr(request, 'user', None)
    request._audit_session_key_at_view = get_session_key(request)


def find_request(args, kwargs):
    if 'request' in kwargs:
        return _normalize_request(kwargs['request'])

    for arg in args:
        request = _normalize_request(arg)
        if request is not None:
            return request

    return get_current_request()


def _normalize_request(request):
    if request is None:
        return None

    if hasattr(request, 'META') and hasattr(request, 'method'):
        return request

    django_request = getattr(request, '_request', None)
    if django_request is not None and hasattr(django_request, 'META'):
        return django_request

    return None


def _is_authenticated_user(user):
    return bool(user is not None and getattr(user, 'is_authenticated', False))


def _username(user):
    getter = getattr(user, 'get_username', None)
    username = getter() if callable(getter) else getattr(user, 'username', '')
    return (username or '')[:150]


def _is_sensitive_key(key):
    if key is None:
        return False

    lowered = str(key).lower()
    sensitive_keys = getattr(settings, 'AUDIT_LOG_SENSITIVE_KEYS', DEFAULT_SENSITIVE_KEYS)
    return any(sensitive_key in lowered for sensitive_key in sensitive_keys)


def _truncate(value, limit=500):
    value = str(value)
    if len(value) <= limit:
        return value
    return f'{value[:limit]}...'


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
