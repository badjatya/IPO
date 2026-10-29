"""NSE stock fetchers for the stock worker (task 014).

Standard-library only in 014; HTTP goes through ``ipo_agent.net.Client``
unchanged. Each module returns plain records keyed by the ``db.md`` column
names. Later tasks add the package's own dependencies through its own
requirements file ([ADR-0026](../../docs/adr/0026-stock-worker-code-location.md)).
"""