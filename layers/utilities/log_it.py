"""Centralize logging by using a decorator
copied from python-layers project"""
import datetime
import json
import logging
import os
import sys
from functools import wraps
from typing import Any


def get_logger(name: str, log_level: str = 'info') -> logging.Logger:
    """Return a logger with the given name and logging level set"""
    handler = logging.StreamHandler(sys.stdout)
    log = logging.getLogger(name)
    log_level = log_level.lower()
    if log_level == 'debug':
        log.setLevel(logging.DEBUG)
        handler.setLevel(logging.DEBUG)
    elif log_level == 'warning':
        log.setLevel(logging.WARNING)
        handler.setLevel(logging.WARNING)
    elif log_level == 'error':
        log.setLevel(logging.ERROR)
        handler.setLevel(logging.ERROR)
    elif log_level == 'critical':
        log.setLevel(logging.CRITICAL)
        handler.setLevel(logging.CRITICAL)
    else:
        log.setLevel(logging.INFO)
        handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(funcName)s - %(lineno)i - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.propagate = False
    return log


LOG_LEVEL = os.environ.get('LOG_LEVEL', 'info').lower()
LOGGER = get_logger(os.path.basename(__file__), LOG_LEVEL)


def log_it(func: Any):
    """Use this decorator to log any method or function
    annotated with @log_it
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        func_str = f'{func.__module__}.{func.__qualname__}'
        line_num_str = f'starting on line {func.__code__.co_firstlineno}'
        if LOG_LEVEL == 'debug':
            args_str = _parse_args(args)
            kwargs_str = _parse_kwargs(kwargs)
        else:
            args_str = _truncate_str(_parse_args(args))
            kwargs_str = _truncate_str(_parse_kwargs(kwargs))
        if kwargs_str:
            args_str += ', ' + kwargs_str
        msg = f'{func_str}({args_str}) {line_num_str}'
        LOGGER.info(msg)
        t_start = datetime.datetime.now()
        result = func(*args, **kwargs)
        t_end = datetime.datetime.now()
        delta = t_end - t_start
        LOGGER.info(f'{msg}: executed in {str(delta.total_seconds())} seconds')
        return result
    return wrapper


def _parse_args(args) -> str:
    sep_char = ''
    result = ''
    for arg in args:
        if isinstance(arg, list):
            for elem in arg:
                result += sep_char + _get_log_str(elem)
        else:
            result += sep_char + _get_log_str(arg)
        sep_char = ', '
    return result


def _parse_kwargs(kwargs) -> str:
    sep_char = ''
    result = ''
    for key, arg in kwargs.items():
        if isinstance(arg, list):
            for elem in arg:
                result += sep_char + key + '=' + _get_log_str(elem)
        else:
            result += sep_char + key + '=' + _get_log_str(arg)
        sep_char = ', '
    return result


def _get_log_str(arg: Any) -> str:
    """Unless the log level is set to debug, replace certain strings
    and truncate at max length to make things more readable
    """
    result = ''
    if isinstance(arg, str):
        result = arg
    elif isinstance(arg, dict):
        result = json.dumps(arg, default=str)
    else:
        result = repr(arg)
    if 'botocore.client.' in result and ' object at ' in result:
        result = f"{result.split(' object at ')[0]}>"
        result = result.replace('botocore.', '').replace(' ', '')
    if LOG_LEVEL == 'debug':
        return result
    return _truncate_str(result)


def _truncate_str(str_to_truncate: str, max_len: int = 150) -> str:
    """Return the given str truncated to the given length"""
    return (str_to_truncate[:max_len] + '...') if len(str_to_truncate) > max_len else str_to_truncate
