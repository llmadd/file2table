import streamlit as st
import pandas as pd
import io
from work.work import NumberService, uploadfile_to_temp
import os

# streamlit应用获取secrets
key=st.secrets['api_key']
base=st.secrets['api_base']
model=st.secrets['model_name']


# 初始化session state
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "api_base" not in st.session_state:
    st.session_state.api_base = ""
if "model_name" not in st.session_state:
    st.session_state.model_name = ""
if "data_type" not in st.session_state:
    st.session_state.data_type = "important"
if "table_type" not in st.session_state:
    st.session_state.table_type = "easy"
if "history_data" not in st.session_state:
    st.session_state.history_data = []  # 用于存储历史数据

# 设置页面标题和图标
st.set_page_config(
    page_title="File2Table - 文件数据提取工具",
    page_icon="📊",
    layout="wide"
)

# 侧边栏配置
with st.sidebar:
    st.title("⚙️ 系统设置")
    
    # API设置
    st.subheader("API 配置")
    st.markdown("可以尝试不设置直接使用，我配置了免费模型资源")
    api_key = st.text_input("API Key", value=st.session_state.api_key, type="password")
    api_base = st.text_input("API Base URL", value=st.session_state.api_base)
    model_name = st.text_input("模型名称", value=st.session_state.model_name)

    st.session_state.api_key = api_key
    st.session_state.api_base = api_base
    st.session_state.model_name = model_name

    # 提取设置
    st.subheader("提取配置")
    data_type = st.radio(
        "数据提取模式",
        options=["important", "detailed"],
        format_func=lambda x: "重要数据" if x == "important" else "详细数据",
        help="选择提取数据的详细程度"
    )
    st.session_state.data_type = data_type
    
    table_type = st.radio(
        "表格格式",
        options=["easy", "with_unit", "with_unit_and_source"],
        format_func=lambda x: {
            "easy": "仅键值对",
            "with_unit": "包含单位",
            "with_unit_and_source": "包含单位和来源"
        }[x],
        help="选择提取数据的格式"
    )
    st.session_state.table_type = table_type
    
    # 关于
    st.markdown("""
                ### 功能计划
                - [ ] 支持更多文件格式(Image/Video)
                - [ ] 支持数据分析汇图
                - [ ] 定制需求，[联系我](https://zhuhai.fun)
                """)

# 主页面
st.title("📊 File2Table")
st.subheader("文件数据智能提取工具")

# 说明文字
st.markdown("""
    👋 欢迎使用 File2Table！
    
    本工具可以帮助您从各种文档中提取结构化数据：
    - 支持 PDF、Word(doc/docx)、TXT 等多种格式
    - 智能识别文档中的关键数据
    - 自动生成表格形式的输出
    - 支持导出 Excel 格式
""")


# 文件上传区域
uploaded_file = st.file_uploader(
    "选择要处理的文件",
    type=["pdf", "txt", "doc", "docx"],
    help="支持PDF、Word和文本文件",
    key="_file"
)

# 操作按钮区域
col1, col2 = st.columns([1, 4])
with col1:
    process_button = st.button("📊 提取数据", type="primary", key="_button")
with col2:
    status_placeholder = st.empty()

# 处理逻辑
if process_button:
    if uploaded_file is not None:
        try:
            # 保存上传的文件到临时文件
            temp_path = uploadfile_to_temp(uploaded_file)
            
            try:
                # 创建服务实例并更新配置
                if st.session_state.api_key:
                    service = NumberService(api_key=st.session_state.api_key, 
                                            api_base=st.session_state.api_base, 
                                            model_name=st.session_state.model_name)
                else:
                    service = NumberService(api_key=key, 
                                            api_base=base, 
                                            model_name=model)
                
                # 读取文件内容
                content = service.file_load(temp_path)
                
                if not content.strip():
                    st.error("⚠️ 文件内容为空")
                    
                # 处理文件内容
                content_list = service.content_split(content)
                
                # 创建进度条
                progress_bar = st.progress(0)
                
                # 处理数据
                generate = service.run(content_list, table_type=st.session_state.table_type, data_type=st.session_state.data_type)
                current_results = []  # 存储当前处理的结果
                
                with st.spinner("🔄 正在处理数据..."):
                    for ind, data in enumerate(generate):
                        if isinstance(data, dict) and "error" not in data:
                            data_list = data["data"]
                            df = pd.DataFrame(data_list)
                            df["文件名"] = uploaded_file.name
                            
                            # 保存当前结果
                            current_results.append({
                                "index": ind + 1,
                                "df": df.copy()
                            })
                            
                            # 更新总表
                            st.session_state["df"] = pd.concat(
                                [st.session_state["df"], df],
                                ignore_index=True
                            )
                            
                            # 更新进度条
                            progress_bar.progress((ind + 1) / len(content_list))
                
                # 将当前结果添加到历史数据中
                if current_results:
                    st.session_state.history_data.append({
                        "file_name": uploaded_file.name,
                        "results": current_results
                    })
                
                # 显示下载按钮
                with status_placeholder:
                    st.success("✅ 数据提取完成！")
                    
                    # 准备Excel下载
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        st.session_state["df"].to_excel(writer, sheet_name='提取数据', index=False)
                    
                    # 提供下载按钮
                    st.download_button(
                        label="⬇️ 下载 Excel 文件",
                        data=buffer.getvalue(),
                        file_name="提取数据.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
            
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_path)
                    os.rmdir(os.path.dirname(temp_path))
                except:
                    pass
                    
        except Exception as e:
            st.error(f"❌ 处理出错: {str(e)}")
    else:
        st.warning("⚠️ 请先上传文件")

# 显示历史数据
if st.session_state.history_data:
    st.markdown("### 📊 历史提取结果")
    for file_data in st.session_state.history_data:
        with st.expander(f"📄 {file_data['file_name']}", expanded=True):
            for result in file_data["results"]:
                st.write(f"数据块 {result['index']} 提取结果")
                st.dataframe(result["df"], use_container_width=True)
                st.divider()

# 页脚
st.markdown("---")
st.markdown("Made with ❤️ by [ZhuHai](https://zhuhai.fun)")
st.markdown("🚀 友情链接：[UseAI](https://useai.cn)")



