# -*- coding: utf-8 -*-
"""
ICAS 运行配置。

将模型与 API 配置集中到环境变量，避免把本地凭证提交到 Git 仓库。
"""

import os

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL_NAME = "ep-20251223144447-7946z"
API_KEY_ENV_VARS = ("ARK_API_KEY", "VOLCENGINE_API_KEY", "ICAS_API_KEY")

BASE_URL = os.getenv("ARK_BASE_URL", DEFAULT_BASE_URL)
MODEL_NAME = os.getenv("ARK_MODEL_NAME", DEFAULT_MODEL_NAME)


def get_api_key():
    """按优先级读取 API Key。"""
    for env_name in API_KEY_ENV_VARS:
        value = os.getenv(env_name)
        if value and value.strip():
            return value.strip()
    return None


def has_api_key():
    """判断当前环境是否已配置 API Key。"""
    return get_api_key() is not None


def require_api_key():
    """读取 API Key；若未配置则抛出可读错误。"""
    api_key = get_api_key()
    if api_key:
        return api_key
    env_names = ", ".join(API_KEY_ENV_VARS)
    raise RuntimeError(f"未配置 API Key，请先设置环境变量之一: {env_names}")
