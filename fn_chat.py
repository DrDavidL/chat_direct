import streamlit as st
import sys

import json
import requests
from datetime import datetime

import ast
import inspect

import openai
import os


import sympy as sp
from sympy import *
from random import randint

if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = ''
    
if 'message_history' not in st.session_state:
    st.session_state.message_history = []
    
if 'query' not in st.session_state:
    st.session_state.query = ''
    
if 'iteration_limit' not in st.session_state:
    st.session_state.iteration_limit = 5
    
if "last_result" not in st.session_state:
    st.session_state.last_result = ""

def check_password():

    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == os.getenv("password"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.write("*Please contact David Liebovitz, MD if you need an updated password for access.*")
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        # fetch_api_key()
        return True

class FunctionWrapper:
	def __init__(self, func):
		self.func = func
		self.info = self.extract_function_info()

	def extract_function_info(self):
		source = inspect.getsource(self.func)
		tree = ast.parse(source)

		# Extract function name
		function_name = tree.body[0].name

		# Extract function description from docstring
		function_description = self.extract_description_from_docstring(self.func.__doc__)

		# Extract function arguments and their types
		args = tree.body[0].args
		parameters = {"type": "object", "properties": {}}
		for arg in args.args:
			argument_name = arg.arg
			argument_type = self.extract_parameter_type(argument_name, self.func.__doc__)
			parameter_description = self.extract_parameter_description(argument_name, self.func.__doc__)
			parameters["properties"][argument_name] = {
				"type": argument_type,
				"description": parameter_description,
			}

		# Extract function return type
		return_type = None
		if tree.body[0].returns:
			return_type = ast.get_source_segment(source, tree.body[0].returns)

		function_info = {
			"name": function_name,
			"description": function_description,
			"parameters": {
				"type": "object",
				"properties": parameters["properties"],
				"required": list(parameters["properties"].keys()),
			},
			"return_type": return_type,
		}

		return function_info

	def extract_description_from_docstring(self, docstring):
		if docstring:
			lines = docstring.strip().split("\n")
			description_lines = []
			for line in lines:
				line = line.strip()
				if line.startswith(":param") or line.startswith(":type") or line.startswith(":return"):
					break
				if line:
					description_lines.append(line)
			return "\n".join(description_lines)
		return None

	def extract_parameter_type(self, parameter_name, docstring):
		if docstring:
			type_prefix = f":type {parameter_name}:"
			lines = docstring.strip().split("\n")
			for line in lines:
				line = line.strip()
				if line.startswith(type_prefix):
					return line.replace(type_prefix, "").strip()
		return None

	def extract_parameter_description(self, parameter_name, docstring):
		if docstring:
			param_prefix = f":param {parameter_name}:"
			lines = docstring.strip().split("\n")
			for line in lines:
				line = line.strip()
				if line.startswith(param_prefix):
					return line.replace(param_prefix, "").strip()
		return None

	# Rest of the class implementation...
	def __call__(self, *args, **kwargs):
		return self.func(*args, **kwargs)

	def function(self):
		return self.info

def function_info(func):
    return FunctionWrapper(func)


message_history = []

def ai(function_name="", query=st.session_state.query):
    function_function = globals().get(function_name)

    # Add the new user message to the history
    
    st.session_state.message_history.append({"role": "user", "content": query})
    # fetch_api_key()
    openai.api_key = st.session_state.openai_api_key   
    
        # Check if message_history is not empty
    if st.session_state.message_history:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=st.session_state.message_history,
            functions=[function_function.function()],
            function_call="auto",
        )



    message = response["choices"][0]["message"]
    first_answer = message["content"]
    if first_answer != st.session_state.last_result:
        st.write(first_answer)
        st.session_state.last_result = first_answer

    # Add the new system message to the history
    st.session_state.message_history.append(message)
    # Step 2, check if the model wants to call a function
    
    if message.get("function_call"):
        function_name = message["function_call"]["name"]
        # st.markdown(f'*No guessing - here is where we use the function call:* **{function_name}**')

        function_function = globals().get(function_name)

        # test we have the function
        if function_function is None:
            print("Couldn't find the function!")
            sys.exit()

        # Step 3, get the function information using the decorator
        function_info = function_function.function()

        # Extract function call arguments from the message
        function_call_args = json.loads(message["function_call"]["arguments"])

        # Filter function call arguments based on available properties
        filtered_args = {}
        for arg, value in function_call_args.items():
            if arg in function_info["parameters"]["properties"]:
                filtered_args[arg] = value

        # Step 3, call the function
        # Note: the JSON response from the model may not be valid JSON
        function_response = function_function(**filtered_args)

        # Step 4, send model the info on the function call and function response
        second_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": query},
                message,
                {
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps(function_response)
                },
            ],
        )
        # st.write(f'here is the second response message: {second_response}')
        message2 = second_response["choices"][0]["message"]
        second_answer = message2["content"]
        if second_answer != st.session_state.last_result:
            st.write(second_answer)
            st.session_state.last_result = second_answer
        st.session_state.message_history.append(message2)
        return second_response
    else:
        return response


# @function_info
# def calculate_expression(expression: str) -> float:
#     """
#     Calculates the result for an expression written in python.

#     :param expression: A mathematical expression written in python
#     :type expression: string
#     :return: A float representing the result of the expression
#     :rtype: float
#     """
#     result = eval(expression)
    
#     return result

@function_info
def calculate_expression(expression: str) -> float:
    """
    Calculates the result for an expression.
    Uses input expressions written for the sympy library.
    For example, cosine is cos (not math.cos) and pi is pi.

    :param expression: A mathematical expression written for the sympy library in python
    :type expression: string
    :return: A float representing the result of the expression
    :rtype: float
    """
    st.info(f'Our current equation: **{expression}**')
    result = float(sp.sympify(expression))
    
    return result


def fetch_api_key():
    api_key = None
    
    try:
        # Attempt to retrieve the API key as a secret
        api_key = st.secrets["OPENAI_API_KEY"]
        # os.environ["OPENAI_API_KEY"] = api_key
        st.session_state.openai_api_key = api_key
        os.environ['OPENAI_API_KEY'] = api_key
        # st.write(f'Here is what we think the key is step 1: {api_key}')
    except:
        
        if st.session_state.openai_api_key != '':
            api_key = st.session_state.openai_api_key
            os.environ['OPENAI_API_KEY'] = api_key
            # If the API key is already set, don't prompt for it again
            # st.write(f'Here is what we think the key is step 2: {api_key}')
            return 
        else:        
            # If the secret is not found, prompt the user for their API key
            st.warning("Oh, dear friend of mine! It seems your API key has gone astray, hiding in the shadows. Pray, reveal it to me!")
            api_key = st.text_input("Please, whisper your API key into my ears: ", key = 'warning2')
  
            st.session_state.openai_api_key = api_key
            os.environ['OPENAI_API_KEY'] = api_key
            # Save the API key as a secret
            # st.secrets["my_api_key"] = api_key
            # st.write(f'Here is what we think the key is step 3: {api_key}')
            return 
    
    return 

# def process_query():
#     query = st.text_input("How can I help you today?")
#     if st.button('Go'):
#         response = ai("calculate_expression", query)
#         # st.write('first response issued ')
#         if response:
#             for choice in response.get('choices'):
#                 # st.write('Here is where we print the response')
#                 st.write(choice.get('message').get('content'))
#     # Add a button to clear the message history
#     if st.button('Clear History'):
#         message_history.clear()

def process_query(query):

    
    done_phrase = "Now we are done."
    if st.button('Go'):
        query = query + " Use the 'calculate_expression' function call to calculate any expression. For trig, use radians. (radians = degrees * pi/180). When your answer is complete, always include ```Now we are done.``` to indicate you are finished."
        i = st.session_state.iteration_limit
        while True:
            response = ai("calculate_expression", query)
            i -= 1
            if i == 0:
                st.write('We are done here - complexity exceeded.')
                break
            if response:
                for choice in response.get('choices'):
                    response_content = choice.get('message').get('content')
                    if response_content != st.session_state.last_result:
                        st.write(response_content)
                        st.session_state.last_result = response_content
                    if done_phrase in response_content:
                        return


    # Add a button to clear the message history


    # if st.button('Download Conversation History'):
    #     conversation_text = '\n'.join([f"Role: {message['role']}, Content: {message['content']}" for message in st.session_state.message_history])
    #     st.download_button(
    #         label="Download Conversation History",
    #         data=conversation_text,
    #         file_name="conversation_history.txt",
    #         mime="text/plain",
    #     )


# Streamlit functions
st.title('Natural Language Calculator and Story Problem Solver')
if check_password():
    fetch_api_key()
    st.info("""Welcome to the Natural Language Calculator and Story Problem Solver. This is a work in progress. Check out the GitHub. 
            As GPT-4 costs $$$ and many problems are multi-step, you have control here to limit the number of iterations.            
            """)
    st.session_state.iteration_limit = st.number_input('Iteration Limit', min_value=1, max_value=10, value=5)
    st.session_state.query = st.text_area("Type a natural language math problem (.e.g, what is the area of a circle with a radius of 4cm), or expression (4 times 6) or give me a story problem to solve. Or, even ask me: Create a story problem and solve it!")
    process_query(st.session_state.query)
    # conversation_text = '\n'.join([f"Role: {message['role']}, Content: {message['content']}" for message in st.session_state.message_history])
    # conversation_text = '\n'.join([f"{message['role']}: {message['content']} \n" for message in st.session_state.message_history])
    # conversation_text = '\n'.join([f"{message['role']}: {message['content']} \n" for message in st.session_state.message_history if message['content'] is not None and message['content'].lower() != 'none'])
    conversation_text = ''
    for message in st.session_state.message_history:
        if message['content'] is not None and message['content'].lower() != 'none':
            # If the keyword is in the message content, split the content at the keyword
            if "Use the 'calculate_expression' function call" in message['content']:
                parts = message['content'].split("Use the 'calculate_expression' function call", 1)
                content = parts[0]
            else:
                content = message['content']
            # Add the content (or the part before the keyword) to the conversation text
            conversation_text += f"{message['role']}: {content} \n\n"




    with st.expander('Conversation History'):
        st.write(conversation_text)
        st.download_button(
            label="Download Conversation History",
            data=conversation_text,
            file_name="conversation_history.txt",
            mime="text/plain",
            )
    if st.button('Clear History'):
        st.session_state.message_history.clear()