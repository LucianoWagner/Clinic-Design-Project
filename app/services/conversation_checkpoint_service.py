import inspect as pyinspect

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlmodel import Session


class ConversationCheckpointService:
    def __init__(self, session: Session, checkpointer=None):
        self.session = session
        self.checkpointer = checkpointer

    async def delete_thread(self, thread_id: str) -> None:
        if await self._delete_with_public_api(thread_id):
            return
        self._delete_postgres_rows(thread_id)

    async def _delete_with_public_api(self, thread_id: str) -> bool:
        if not self.checkpointer:
            return False

        for method_name in ("adelete_thread", "delete_thread"):
            method = getattr(self.checkpointer, method_name, None)
            if not callable(method):
                continue
            try:
                result = method(thread_id)
                if pyinspect.isawaitable(result):
                    await result
                return True
            except (NotImplementedError, AttributeError, TypeError):
                continue
        return False

    def _delete_postgres_rows(self, thread_id: str) -> None:
        bind = self.session.get_bind()
        if bind.dialect.name != "postgresql":
            return

        inspector = sa_inspect(bind)
        for table_name in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            if inspector.has_table(table_name):
                self.session.execute(
                    text(f"DELETE FROM {table_name} WHERE thread_id = :thread_id"),
                    {"thread_id": thread_id},
                )
