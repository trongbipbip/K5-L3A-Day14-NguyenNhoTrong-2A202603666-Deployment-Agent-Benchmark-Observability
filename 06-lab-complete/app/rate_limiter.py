"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""


import hashlib
import secrets
import time

from fastapi import HTTPException
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import r


_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
local n = redis.call('ZCARD', KEYS[1])
if n >= tonumber(ARGV[3]) then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  return {0, oldest[2]}
end
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[4])
redis.call('EXPIRE', KEYS[1], 61)
return {1, 0}
"""


def check_rate_limit(key: str) -> None:
    now = time.time()
    redis_key = "rate:" + hashlib.sha256(key.encode()).hexdigest()
    try:
        allowed, oldest = r.eval(_SCRIPT, 1, redis_key, now - 60, now,
                                 settings.rate_limit_per_minute, f"{now}:{secrets.token_hex(8)}")
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable") from exc
    if not allowed:
        retry = max(1, int(float(oldest) + 60 - now) + 1)
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": str(retry)})
