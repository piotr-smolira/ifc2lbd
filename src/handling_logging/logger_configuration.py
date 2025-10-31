# The file was originally written by https://github.com/mCodingLLC/
# Inspired by YouTube video: https://youtu.be/9L77QExPmI0
# It contains slight modifications

import sys
import datetime as dt
import json
import logging
from logging.handlers import QueueHandler, QueueListener
from typing import override

LOG_RECORD_BUILTIN_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class JSONFormatter(logging.Formatter):
    def __init__(
            self,
            *,
            fmt_keys: dict[str, str] | None = None,
    ):
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    @override
    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: logging.LogRecord):
        always_fields = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }
        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: msg_val
            if (msg_val := always_fields.pop(val, None)) is not None
            else getattr(record, val)
            for key, val in self.fmt_keys.items()
        }
        message.update(always_fields)

        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message


"""
class NonErrorFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool | logging.LogRecord:
        return record.levelno <= logging.INFO
"""


class LevelFilter(logging.Filter):
    def __init__(self, level):
        super().__init__()
        self.level = getattr(logging, level)

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self.level


class ModuleFilter(logging.Filter):
    def __init__(self, name='', include_modules=None, exclude_modules=None):
        super().__init__(name)
        self.include_modules = include_modules if include_modules else []
        self.exclude_modules = exclude_modules if exclude_modules else []

    def filter(self, record):
        if record.module in self.exclude_modules:
            return False
        if not self.include_modules or record.module in self.include_modules or record.funcName in self.include_modules:
            return True
        return False


class NameFilter(logging.Filter):
    def __init__(self, name='', include_names=None, exclude_names=None):
        super().__init__(name)
        self.include_names = include_names if include_names else []
        self.exclude_names = exclude_names if exclude_names else []

    def filter(self, record):
        if record.name in self.exclude_names:
            return False
        if not self.include_names or record.name in self.include_names:
            return True
        return False


class DynamicFilter(logging.Filter):
    def __init__(self, name='', include_modules=None, exclude_modules=None, include_names=None, exclude_names=None):
        super().__init__(name)
        self.include_modules = include_modules or []
        self.exclude_modules = exclude_modules or []
        self.include_names = include_names or []
        self.exclude_names = exclude_names or []

    def filter(self, record):
        if self.include_modules and record.module not in self.include_modules:
            return False
        if self.exclude_modules and record.module in self.exclude_modules:
            return False
        if self.include_names and record.name not in self.include_names:
            return False
        if self.exclude_names and record.name in self.exclude_names:
            return False
        return True


"""
class InfoDebugHandler(logging.StreamHandler):
    def emit(self, record):
        if record.levelno in (logging.INFO, logging.DEBUG):
            super().emit(record)


class WarningErrorCriticalHandler(logging.StreamHandler):
    def emit(self, record):
        if record.levelno >= logging.WARNING:
            super().emit(record)

"""
