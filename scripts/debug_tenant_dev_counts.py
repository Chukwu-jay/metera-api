import asyncio
import os
import asyncpg


async def main():
    conn = await asyncpg.connect(os.environ["METERA_POLICY_STORE_DSN"])
    row = await conn.fetchrow(
        """
        SELECT count(*) AS c,
               min(request_id) AS min_id,
               max(request_id) AS max_id,
               min(observed_at) AS min_ts,
               max(observed_at) AS max_ts,
               count(distinct request_id) AS dc
        FROM request_ledger
        WHERE tenant_id = 'tenant_dev'
        """
    )
    print(dict(row))
    rows = await conn.fetch(
        """
        SELECT substring(request_id from 1 for 20) AS prefix, count(*) AS c
        FROM request_ledger
        WHERE tenant_id = 'tenant_dev'
        GROUP BY 1
        ORDER BY 2 DESC, 1
        """
    )
    for r in rows:
        print(dict(r))
    await conn.close()


asyncio.run(main())
