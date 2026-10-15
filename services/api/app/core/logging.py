import logging
import sys

from pythonjsonlogger.json import JsonFormatter

from app.core.config import settings
from app.core.request_context import request_id_var, user_id_var, workspace_id_var


class ContextFilter(logging.Filter):
    """Attach request/user/workspace ids to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.workspace_id = workspace_id_var.get()
        return True


def setup_logging(level: str | int | None = None) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(ContextFilter())
    if settings.use_json_logs:
        handler.setFormatter(
            JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s "
                "%(request_id)s %(user_id)s %(workspace_id)s",
                rename_fields={"levelname": "level", "asctime": "time", "name": "logger"},
            ),
        )
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] rid=%(request_id)s %(message)s"
            ),
        )

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level or settings.log_level.upper())
    # Uvicorn's own access log duplicates our request log line.
    logging.getLogger("uvicorn.access").disabled = True
