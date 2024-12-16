from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel, Field
from typing import Union, Optional, List
import fitz
from ._PROMPT import *
import json
import docx
import io
from streamlit.runtime.uploaded_file_manager import UploadedFile
import tempfile
import os
from dotenv import load_dotenv

load_dotenv()

class DataWithUnitAndSource(BaseModel):
    key: str = Field(description="字段名")
    value: Union[int, float] = Field(description="字段数值")
    unit: str = Field(description="数值单位")
    source: str = Field(description="数据来源")

class DataWithUnit(BaseModel):
    key: str = Field(description="字段名")
    value: Union[int, float] = Field(description="字段数值")
    unit: str = Field(description="数值单位")

class EasyData(BaseModel):
    key: str = Field(description="字段名")
    value: Union[int, float] = Field(description="字段数值")



def uploadfile_to_temp(file_obj: UploadedFile) -> str:
    """将上传的文件保存为临时文件并返回路径"""
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file_obj.name)
    with open(temp_path, 'wb') as f:  # 移除encoding参数，因为是二进制写入
        f.write(file_obj.read())
    return temp_path


class NumberService:
    
    def __init__(self, api_key: str = os.getenv("OPENAI_API_KEY"), 
                 api_base: str = os.getenv("OPENAI_API_BASE"), 
                 model_name: str = os.getenv("OPENAI_MODEL_NAME")):
        self.client = OpenAI(
            api_key = api_key,
            base_url = api_base
        )
        self.model_name = model_name
        print(self.model_name)
    def file_load(self, file_path: str) -> str:
        """从文件路径读取内容"""
        file_content = ""
        # 转换文件路径为小写来进行判断
        file_path_lower = file_path.lower()
        
        try:
            if file_path_lower.endswith('.pdf'):
                doc = fitz.open(file_path)
                for page in doc:
                    text = page.get_text()
                    file_content += text
                doc.close()
                return file_content
            
            elif file_path_lower.endswith('.txt'):
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()
            
            elif file_path_lower.endswith('.docx'):
                # 处理 .docx 文件
                doc = docx.Document(file_path)
                for para in doc.paragraphs:
                    file_content += para.text + "\n"
                return file_content
            
            elif file_path_lower.endswith('.doc'):
                # 处理 .doc 文件
                import platform
                if platform.system() == 'Windows':
                    try:
                        from win32com import client
                        word = client.Dispatch('Word.Application')
                        try:
                            word.Visible = False
                            doc = word.Documents.Open(file_path)
                            file_content = doc.Content.Text
                            doc.Close()
                            return file_content
                        finally:
                            word.Quit()
                    except Exception as e:
                        raise ValueError(f"处理 .doc 文件失败，请确保安装了 Microsoft Word: {str(e)}")
                else:
                    raise ValueError("当前应用环境为Linux不支持 .doc 格式，请转换为 .docx 格式后再试")
            
            else:
                raise ValueError(f"不支持的文件类型: {file_path}")
                
        except Exception as e:
            raise ValueError(f"文件读取失败: {str(e)}")

    def content_split(self, content: str, max_length: int = 3000) -> List[str]:
        # 首先尝试用\n\n分割
        chunks = content.split("\n\n")
        result = []
        
        for chunk in chunks:
            if len(chunk) <= max_length:
                if chunk.strip():  # 确保不添加空字符串
                    result.append(chunk)
            else:
                # 如果chunk超过3000，用\n继续分割
                sub_chunks = chunk.split("\n")
                current_chunk = ""
                
                for sub_chunk in sub_chunks:
                    if len(current_chunk) + len(sub_chunk) + 1 <= max_length:
                        if current_chunk:
                            current_chunk += "\n"
                        current_chunk += sub_chunk
                    else:
                        if current_chunk:
                            result.append(current_chunk)
                        current_chunk = sub_chunk
                
                if current_chunk:  # 添加最后一个chunk
                    result.append(current_chunk)
        
        return result
    
    def run(self, content: List[str], table_type: str = "easy", data_type: str = "important"):
        
        if table_type == "easy":
            class DataList(BaseModel):
                data: List[EasyData] = Field(..., description="数据列表")
        elif table_type == "with_unit":
            class DataList(BaseModel):
                data: List[DataWithUnit] = Field(..., description="数据列表")
        elif table_type == "with_unit_and_source":
            class DataList(BaseModel):
                data: List[DataWithUnitAndSource] = Field(..., description="数据列表")
        
        if data_type == "important":
            prompt = IMPORTANT_PROMPT
        elif data_type == "detailed":
            prompt = DETAILED_PROMPT
        else:
            raise ValueError("不支持的数据类型")

        for page_content in content:
            messages = [
                {"role": "user", "content": prompt.format(content = page_content)}
            ]
            try:
                if "gpt-4o" in self.model_name:
                    response = self.client.beta.chat.completions.parse(
                        model = self.model_name,
                        messages = messages,
                        response_format = DataList,

                    )
                else:
                    response = self.client.chat.completions.create(
                        model = self.model_name,
                        messages = messages,
                        extra_body = {
                            "guided_json": DataList.model_json_schema() 
                        }
                    )
            except Exception as e:
                raise ValueError(f"模型请求失败（ps:现在仅支持gpt-4o模型和vllm兼容openai部署模型）: {str(e)}")

            try:
                answer = response.choices[0].message.content
                answer_dict = json.loads(answer)
                print(answer_dict)
                yield answer_dict
            except Exception as e:
                yield {"error": str(e)}


