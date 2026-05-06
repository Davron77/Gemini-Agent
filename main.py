import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from termcolor import colored
import json

# Import your tool definition
from tools import read_file_definition, list_files_definition, edit_file_definition, search_documentation_definition

# Load variables from .env into the environment
load_dotenv()

class GeminiAgent:
    def __init__(self):

        api_key = os.getenv("GEMINI_API_KEY")

        self.client = genai.Client(api_key=api_key)
        self.model_id = 'gemini-3-flash-preview'

        
        # 1. Register tools in a dictionary for easy access
        self.registry = {
            read_file_definition.name: read_file_definition,
            list_files_definition.name: list_files_definition,
            edit_file_definition.name: edit_file_definition,
            search_documentation_definition.name: search_documentation_definition,
        }

        # 2. Build the declarations for the API config
        declarations = [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema
            } for tool in self.registry.values()
        ]
        
        self.config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=declarations)],
            max_output_tokens=500, # Set the limit here
            temperature=0.7                # Optional: controls creativity
        )
        self.history = []

    def execute_tool(self, function_call):
        """
        Handles the actual execution of the local Python logic.
        """
        name = function_call.name
        args = function_call.args # This is already a dict from Gemini

        if name not in self.registry:
            return f"Error: Tool '{name}' not found."

        tool_def = self.registry[name]
        
        print(colored(f"  [Action]: Executing {name} with args {args}...", "magenta"))

        # Since your current tool functions expect a JSON string, we dump it
        # Pro-tip: You could refactor your tools to accept a dict to skip this step
        content, error = tool_def.function(json.dumps(args))
        
        if error:
            return f"Error executing {name}: {error}"
        return content

    def run(self):
        print(colored('Gemini: "Hi!"', 'red', attrs=['bold']))

        while True:
            user_input = input(colored('\nYou: ', 'blue'))
            if user_input.lower() in ['exit', 'quit']: break

            self.history.append(types.Content(role="user", parts=[types.Part.from_text(text=user_input)]))

            # Initial call to the model
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=self.history,
                config=self.config
            )

            # Function Calling Loop
            while response.candidates[0].content.parts[0].function_call:
                call = response.candidates[0].content.parts[0].function_call
                
                # Acknowledge the call in history
                self.history.append(response.candidates[0].content)

                # --- USE THE NEW EXECUTE METHOD ---
                tool_result = self.execute_tool(call)

                # Create the response part
                response_part = types.Part.from_function_response(
                    name=call.name,
                    response={'result': tool_result}
                )
                
                self.history.append(types.Content(role="tool", parts=[response_part]))
                
                # Get the next response from Gemini based on the tool output
                response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=self.history,
                    config=self.config
                )

            # Output the final reasoned response
            if response.text:
                print(colored('Gemini:', 'yellow'), f' {response.text}')
                self.history.append(response.candidates[0].content)

if __name__ == '__main__':
    GeminiAgent().run()