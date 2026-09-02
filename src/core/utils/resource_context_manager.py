from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from types import TracebackType
from typing import TypeVar

ResourceT = TypeVar("ResourceT")


class ResourceContextManager:
    """
    Generic scoped resource manager.

    Resources registered with this manager are released deterministically
    when the context exits. Resources are released in reverse registration
    order.

    The manager itself is intentionally scoped to a single operation and
    must not be shared between threads or ingestion jobs.
    """

    def __init__(self) -> None:
        self._stack = ExitStack()
        self._entered = False

    def __enter__(self) -> ResourceContextManager:
        if self._entered:
            raise RuntimeError(
                "ResourceContextManager cannot be entered more than once.",
            )

        self._entered = True
        self._stack.__enter__()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self._stack.__exit__(
                exc_type,
                exc_value,
                traceback,
            )
        finally:
            self._entered = False

    def register(
        self,
        resource: ResourceT,
        *,
        close: Callable[[ResourceT], object] | None = None,
    ) -> ResourceT:
        """
        Register an already-created resource.

        Args:
            resource:
                Resource to manage.

            close:
                Optional custom cleanup function. When omitted, the
                resource must expose a callable ``close()`` method.

        Returns:
            The same resource instance.

        Raises:
            RuntimeError:
                If called outside an active context.

            TypeError:
                If the resource has no usable cleanup operation.
        """

        if not self._entered:
            raise RuntimeError(
                "Resources can only be registered inside an active "
                "ResourceContextManager context.",
            )

        if close is None:
            close_method = getattr(
                resource,
                "close",
                None,
            )

            if not callable(close_method):
                raise TypeError(
                    f"Resource of type {type(resource).__name__} "
                    "does not provide a callable close() method. "
                    "Provide a custom close callback.",
                )

            self._stack.callback(close_method)

        else:
            self._stack.callback(
                close,
                resource,
            )

        return resource

    def create(
        self,
        factory: Callable[[], ResourceT],
        *,
        close: Callable[[ResourceT], object] | None = None,
    ) -> ResourceT:
        """
        Create and immediately register a resource.

        If resource creation succeeds, ownership is transferred to this
        manager.
        """

        resource = factory()

        try:
            return self.register(
                resource,
                close=close,
            )
        except BaseException:
            # Registration failed, so the manager does not own the
            # resource. Clean it up immediately.
            cleanup = close or getattr(
                resource,
                "close",
                None,
            )

            if not callable(cleanup):
                raise

            cleanup(resource) if close else cleanup()
            raise
