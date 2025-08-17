# feishu_agent.py
import json
import requests
import pandas as pd
from datetime import datetime

# 你的 App ID 和 App Secret
app_id = "cli_a6632eded6b8100e"
app_secret = "SJuUTFaLyxKBpU8I9Q1DdtjrrDB4NCbN"

# 你的 App Token 和 Table ID
app_token = "POVDbwY7paHthsspJknclP3Unfb"
table_id = "tblXNF3B7sKO1AyJ"


def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = json.dumps({"app_id": app_id, "app_secret": app_secret})
    response = requests.post(url, headers=headers, data=data)
    response_json = response.json()
    if response_json.get("code") == 0:
        return response_json.get("tenant_access_token")
    else:
        print(f"Error getting tenant access token: {response_json}")
        return None


def get_bitable_records(tenant_access_token, app_token, table_id, page_size=500, page_token=None):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
    headers = {
        "Authorization": f"Bearer {tenant_access_token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    params = {"page_size": page_size}
    if page_token:
        params["page_token"] = page_token

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        response_json = response.json()
        if response_json.get("code") == 0:
            return response_json.get("data")
        else:
            print(f"Error getting bitable records: {response_json}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None


def get_all_bitable_records(tenant_access_token, app_token, table_id):
    all_records = []
    page_token = None
    has_more = True

    while has_more:
        data = get_bitable_records(tenant_access_token, app_token, table_id, page_token=page_token)
        if data:
            records = data.get("items", [])
            all_records.extend(records)
            page_token = data.get("page_token")
            has_more = data.get("has_more")
        else:
            break
    return all_records


def records_to_dataframe(records):
    """将飞书 bitable 的 records 转换为 Pandas DataFrame"""
    rows = []
    for rec in records:
        fields = rec.get("fields", {})

        row = {}

        # 日期（转 datetime）
        if "日期" in fields and isinstance(fields["日期"], (int, float)):
            row["日期"] = datetime.fromtimestamp(fields["日期"] / 1000)
        else:
            row["日期"] = None

        # 一级分类
        row["一级分类"] = fields.get("一级分类")

        # 金额
        try:
            row["金额"] = float(fields.get("金额")) if fields.get("金额") else None
        except ValueError:
            row["金额"] = None

        # 备注
        row["备注"] = fields.get("备注")

        rows.append(row)

    return pd.DataFrame(rows, columns=["日期", "一级分类", "金额", "备注"])
