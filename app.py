import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from feishu_agent import (
    get_tenant_access_token,
    get_all_bitable_records,
    records_to_dataframe,
    app_id,
    app_secret,
    app_token,
    table_id,
)
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI

# ===================== Matplotlib 中文设置 =====================
plt.rcParams['font.sans-serif'] = ['SimHei']  # 或 'Microsoft YaHei'
plt.rcParams['axes.unicode_minus'] = False   # 解决负号显示为方块

# 初始化 Streamlit 页面
st.set_page_config(page_title="飞书问答助手", layout="wide")
st.title("📊 飞书多维表格问答助手")

# ===================== 侧边栏：加载数据 =====================
with st.sidebar:
    st.header("数据加载")
    if st.button("从飞书获取最新数据"):
        token = get_tenant_access_token(app_id, app_secret)
        if token:
            records = get_all_bitable_records(token, app_token, table_id)
            if records:
                df = records_to_dataframe(records)
                st.session_state["df"] = df
                st.success(f"✅ 成功获取 {len(df)} 条记录")
            else:
                st.error("❌ 获取记录失败")
        else:
            st.error("❌ 获取 Tenant Access Token 失败")

# ===================== 主页面 =====================
if "df" not in st.session_state:
    st.warning("请先在侧边栏点击按钮获取数据")
else:
    df = st.session_state["df"]
    st.write("### 数据预览")
    st.dataframe(df.head(10))

    # 初始化 LLM + Agent
    if "agent" not in st.session_state:
        llm = ChatOpenAI(
            model="deepseek-chat",
            api_key=st.secrets["PROXY_API_KEY"],  # ✅ 用 secrets 管理
            base_url="https://api.deepseek.com",
            temperature=0,
        )
        agent = create_pandas_dataframe_agent(
            llm=llm,
            df=df,
            verbose=True,
            allow_dangerous_code=True,
            return_intermediate_steps=True  # ✅ 确保能拿到 thought
        )
        st.session_state["agent"] = agent

    # 输入问题
    CSV_PROMPT_PREFIX = """
    First set the pandas display options to show all the columns,
    get the column names, then answer the question.
    """

    CSV_PROMPT_SUFFIX = """
    - **ALWAYS** before giving the Final Answer, try another method.
    Then reflect on the answers of the two methods you did and ask yourself
    if it answers correctly the original question.
    If you are not sure, try another method.
    - If the methods tried do not give the same result,reflect and
    try again until you have two methods that have the same result.
    - If you still cannot arrive to a consistent result, say that
    you are not sure of the answer.
    - If you are sure of the correct answer, create a beautiful
    and thorough response using Markdown.
    - **DO NOT MAKE UP AN ANSWER OR USE PRIOR KNOWLEDGE,
    ONLY USE THE RESULTS OF THE CALCULATIONS YOU HAVE DONE**.
    - output with Chinese.

    ---------------------- **ALWAYS**
    """


    # ===================== 问答区域 =====================
    st.write("### 问答")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    # chat_input 会悬浮在页面底部，并自带发送按钮
    user_query = st.chat_input("请输入你的问题，例如：上个月消费总额是多少？")

    if user_query:
        with st.spinner("正在思考..."):
            response = st.session_state["agent"].invoke(
                CSV_PROMPT_PREFIX + user_query + CSV_PROMPT_SUFFIX
            )

        # 保存 thought 和 charts
        thoughts, charts = [], []
        for step in response.get("intermediate_steps", []):
            thought_text = step[0].log if hasattr(step[0], "log") else str(step[0])
            thoughts.append(thought_text)

            # 保存 matplotlib 图表
            fig = plt.gcf()
            buf = BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            buf.seek(0)
            charts.append(buf)
            plt.close(fig)

        # 保存到历史记录
        st.session_state["chat_history"].append({
            "query": user_query,
            "thoughts": thoughts,
            "charts": charts,
            "final_answer": response["output"]
        })

    # 瀑布流展示历史记录
    for idx, record in enumerate(st.session_state["chat_history"]):
        st.markdown(f"### 💬 问题 {idx+1}")
        st.info(record["query"])

        st.success("🧩 思考过程 (Thought)")
        for i, t in enumerate(record["thoughts"]):
            st.markdown(f"**Step {i+1}:** {t}")
            if i < len(record["charts"]):
                st.image(record["charts"][i])

        st.success("🎯 最终答案 (Final Answer)")
        st.write(record["final_answer"])

