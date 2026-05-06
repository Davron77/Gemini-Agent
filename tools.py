import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from rag import WeaviateRag

class ToolDefinition:
    def __init__(self, name, description, input_schema, function):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.function = function

def read_file(input_data):
    input_dict = json.loads(input_data)
    path = input_dict['path']

    try:
        with open(path, 'r') as file:
            content = file.read()
            return content, None
        
    except Exception as e:
        return '', str(e)

def list_files(input_data):
    input_dict = json.loads(input_data) if input_data else {}
    base_path = input_dict.get('path', '.')

    try:
        result = []

        for root, _, filenames in os.walk(base_path):
            if base_path == "." :
                relative_dir = "."
            else:
                relative_dir = os.path.relpath(root, base_path)
            
            if relative_dir != ".":
                result.append(f"{relative_dir}/")

            for filename in filenames:
                if relative_dir == ".":
                    result.append(filename)
                else:
                    result.append(os.path.join(relative_dir, filename))
        
        return json.dumps(result), None

    except Exception as e:
            return '', str(e)

def edit_file(input_data):
    input_dict = json.loads(input_data)
    path = input_dict['path']
    old_str = input_dict['old_str']
    new_str = input_dict['new_str']

    if not path or old_str == new_str:
        return "", "invalid input params"
    
    file_path = Path(path)

    try:
        if not os.path.exists(file_path) and old_str == "":
            if file_path.parent != Path("."):
                file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(new_str)

            return f"Successfully created file {path}", None
        
        content = file_path.read_text()

        if old_str not in content and old_str != "":
            return "", "old_str not found in the file"
        
        new_content = content.replace(old_str, new_str)
        file_path.write_text(new_content)

        return "Successfully edited.", None

    except Exception as e:
        return "", str(e)

def search_documentation(input_data):
    input_dict = json.loads(input_data)
    query = input_dict["query"]
    top_k = input_dict.get("top_k", 3)

    try:
        with WeaviateRag() as rag:
            results = rag.search(query, top_k)

            if not results:
                return "No relevant documentation found.", None
            
            formatted_result = []

            for i, result in enumerate(results):
                formatted_result.append(
                    f"Result {i} - {result['filename']}, chunk {result['chunk_id']}\n"
                    f"{result['content']}"
                )
            
        
        return "\n ---- \n".join(formatted_result), None
    
    except Exception as e:
        return "", f"Search failed: {e}"

class ReadFileInput(BaseModel):
    path: str = Field(
        description='The relative path of a file in the working directory.'
    )

class ListFilesInput(BaseModel):
    path: Optional[str] = Field(
        description="Optional relative path to list files from. Defaults to the current directory if not provided.",
        default=None
    )

class EditFileInput(BaseModel):
    path: str = Field(
        description="The path to the file. If it doesn't exist, the tool creates it automatically."
    )
    old_str: str = Field(
        description="Text to search for - must match exactly and must only have one match exactly."
    )
    new_str: str = Field(description="Text to replace old_str with.")

class SearchDocumentationInput(BaseModel):
    query: str = Field(
        description="The search query describing the information you are looking for"
    )
    top_k: Optional[int] = Field(
        description="Number of relevant documentation chunks to return", default=3
    )

read_file_definition = ToolDefinition(
    name='read_file',
    description="Read the contents of a given relative file path. Use this when you eant to see what's inside a file. Do not use this with directory names.",
    input_schema=ReadFileInput.model_json_schema(),
    function=read_file,
)

list_files_definition = ToolDefinition(
    name="list_files",
    description="List files and directories at a given path. If no path is provided, list files in the current directory.",
    input_schema=ListFilesInput.model_json_schema(),
    function=list_files
)

edit_file_definition = ToolDefinition(
    name="edit_file",
    description="""Make edits to a file.
    Replaces 'old_str' with 'new_str' in the given file. 'old_str' and 'new_str' MUST be different from each other.
    If the file specified with path doesn't exist, it will be created automatically.
    """,
    input_schema=EditFileInput.model_json_schema(),
    function=edit_file,
)

search_documentation_definition = ToolDefinition(
    name="search_documentation",
    description="Search through project documentation to find relevant information. Use this tool when you need to answer questions about the project, features, setup, configuration and etc.",
    input_schema=SearchDocumentationInput.model_json_schema(),
    function=search_documentation,
)