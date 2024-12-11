# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pandas",
#     "requests",
#     "matplotlib",
#     "seaborn",
#     "numpy",
#     "scipy",
#     "scikit-learn",
# ]
# ///

"""
This script performs a comprehensive data analysis workflow, including:

1. Reading a CSV dataset provided as a command-line argument.
2. Conducting exploratory data analysis (EDA) to generate an overview of the data, including summary statistics, null values, outliers, etc.
3. Using GPT-based APIs to suggest further analysis, generate Python code for the analysis, and create a story based on the findings.
4. Visualizing key insights through recommended graphs and saving them as images. (ensuring the graphs are with titles, axis labels, legends, and annotations, and uses colors effectively where applicable)
5. Producing a markdown report that combines the EDA, analysis, and visualizations into a cohesive narrative.

The script dynamically handles errors in data reading and API interactions, ensures compatibility with different encodings, and provides user-friendly outputs to facilitate data storytelling.
"""


import sys
import pandas as pd
import os
import requests
import json
import io
import matplotlib
import seaborn
import numpy as np

# Entry point to handle file input and API key
try:
    file_name = sys.argv[1]

    try:
        df = pd.read_csv(file_name)
    except UnicodeDecodeError:
        df = pd.read_csv(file_name, encoding="latin-1")

    # api_key = os.environ.get("AIPROXY_TOKEN")
    api_key = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIyZjIwMDA3MTNAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.fqrCmspjhPTZe5AvhHqVkpASOq78Y6IFFiharI6R0Go"
    if not api_key:
        raise ValueError("ERROR: API key not found in environment variables")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)


# Functions
def ask_gpt_4o_mini(data, count=0):
    """Send a request to GPT-4o-mini and handle retries."""
    url = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            return response.json()
        else:
            if count < 10:
                print("Retrying request...")
                return ask_gpt_4o_mini(data, count + 1)
            else:
                print(f"Error: {response.status_code}")
                print(response.text)
                return None
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

def exec_code(code_string):
    """Execute Python code and return its output."""
    output = io.StringIO()
    sys.stdout = output

    try:
        exec(code_string)
    finally:
        sys.stdout = sys.__stdout__

    captured_output = output.getvalue()
    output.close()
    return captured_output

def detect_iqr_outliers(df):
    """Detect outliers in numerical columns using the IQR method."""
    outliers = {}
    numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    for col in numerical_cols:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        outliers_in_col = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
        outlier_count = outliers_in_col.shape[0]
        outlier_percentage = (outlier_count / df.shape[0]) * 100

        outliers[col] = {
            'count': outlier_count,
            'percentage': outlier_percentage
        }

    return outliers

def make_prompt(file):
    """Generate a summary of the dataset for prompting LLMs."""
    try:
        df = pd.read_csv(file)
    except UnicodeDecodeError:
        df = pd.read_csv(file, encoding="latin-1")

    shape = df.shape
    columns = list(df.columns)
    dtypes = list(df.dtypes.values)
    describe = df.describe()

    # File Name
    file_name = f"Filename: {file}\n"

    # Data Overview
    data_overview = f"Data Overview\nShape of the data: {shape[0]} rows and {shape[1]} columns\nColumns: "
    data_overview += ", ".join([f"'{columns[ind]}' ({dtypes[ind]})" for ind in range(len(columns))])

    # Descriptive Statistics
    desc_numerical = f"Descriptive Statistics of numerical features (output of df.describe())\n{describe}\n"

    # Descriptive Stats of Categorical Data
    desc_categorical = "Descriptive statistics of categorical features\n"
    for ind, col in enumerate(columns):
        if dtypes[ind] == "object":
            uniq_vals = len(df[col].unique())
            if uniq_vals < 30:
                values = df[col].value_counts().iloc[:5].index
                counts = df[col].value_counts().iloc[:5].values
                desc_categorical += f"'{col}': {uniq_vals} unique values => "
                desc_categorical += ", ".join([f"('{values[j]}': {counts[j]})" for j in range(len(values))])
            else:
                desc_categorical += f"'{col}': {uniq_vals} unique values"
            desc_categorical += "\n"

    # Null Values
    null_vals = "Null Values\n" + "\n".join(
        [f"'{col}': {df[col].isna().sum()} null values" for col in columns if df[col].isna().sum() > 0]
    )

    # Outliers
    outliers = detect_iqr_outliers(df)
    outlier_txt = "Outlier Detection\n" + "\n".join(
        [
            f"'{col}': {data['count']} outliers detected, comprising {data['percentage']:.2f}% of total values"
            for col, data in outliers.items() if data['count'] > 0
        ]
    )

    # Create the prompt
    prompt = "\n\n".join([file_name, data_overview, desc_numerical, desc_categorical, null_vals, outlier_txt])
    return prompt

# Generate prompt and save the initial README
prompt = make_prompt(file_name)
with open("README.md", "w") as f:
    f.write(prompt)


# Use GPT to generate analysis suggestions
chat_history = [
    {
        "role": "system",
        "content": """
You are a Brilliant Data Scientist. You take the Exploratory Data Analysis (EDA) of any dataset as input and suggest 5 essential analyses to create a comprehensive story of the data. 

**Key Instructions**:
- Avoid suggesting correlation analysis.
- Your output should consist only of the analysis names, listed as bullet points.
- Example: 
    - 1. Time Series Analysis
        """
    },
    {
        "role": "user",
        "content": f"EDA of the dataset:\n{prompt}"
    },
]


data = {
    "model": "gpt-4o-mini",  # Specify the model
    "messages": chat_history,
    "temperature": 0.7  # Adjust the creativity of the response
}

response = ask_gpt_4o_mini(data)
analysis_to_perform = response['choices'][0]['message']["content"]


# Generate analysis code
chat_history = [
    {
        "role": "system",
        "content": """
You are a Brilliant Data Scientist. You take the Exploratory Data Analysis (EDA) of any dataset as input along with a list of analyses to perform on the data and output Python code to execute these analyses.
- **Note 1**: The code you provide must not generate image outputs. Instead, the code should print all results when executed using `exec()`.
- **Note 2**: Your response should contain only the code requested, without any additional commentary. 
    - Example: **Input**: "code to print hello world" | **Output**: `print("hello world")`
- **Note 3**: Ensure the code is error-free by incorporating `try` and `except` blocks where necessary, keeping it simple and robust.
- **Note 4**: Handle the dataset file with the following logic:
    - First, attempt to load the dataset using UTF-8 encoding.
    - If a `UnicodeDecodeError` occurs, fallback to using `latin-1` encoding.
- **Note 5**: Ensure numeric analyses are applied only to numeric columns in the dataset.
        """
    },
    {
        "role": "user",
        "content": f"EDA of the dataset:\n{prompt}"
    },
    {
        "role": "user",
        "content": f"Analysis to perform:\n{analysis_to_perform}"
    },
]

data = {
    "model": "gpt-4o-mini",  # Specify the model
    "messages": chat_history,
    "temperature": 0.7  # Adjust the creativity of the response
}

response = ask_gpt_4o_mini(data)
code = response['choices'][0]['message']["content"]
clean_code = code.replace("`", "").replace("python", "")
analysis_output = exec_code(clean_code)


## GPT for creating initial story
chat_history = [
    {
        "role": "system",
        "content": """
You are a Brilliant Data Scientist with expertise in data storytelling. You take the Exploratory Data Analysis (EDA) of a dataset and the results of various analyses as input to create a compelling story that explains the dataset and provides meaningful insights.
- Note 1: Ignore any analysis that does not yield results or is unavailable.
- Note 2: The story should integrate the dataset's characteristics, the analysis performed, and any significant findings to provide a clear and engaging narrative.
- Note 3: Output must be in Markdown format (`.md`) and structured for readability and professional presentation.
        """
    },
    {
        "role": "user",
        "content": f"The EDA of the dataset:\n{prompt}"
    },
    {
        "role": "user",
        "content": f"The analyses we tried to perform:\n{analysis_to_perform}"
    },
    {
        "role": "user",
        "content": f"The output of the analyses:\n{analysis_output}"
    },
]

data = {
    "model": "gpt-4o-mini",  # Specify the model
    "messages": chat_history,
    "temperature": 0.7  # Adjust the creativity of the response
}

response = ask_gpt_4o_mini(data)
dataset_story = response['choices'][0]['message']["content"]


## GPT for finding important graphs for the story
chat_history = [
    {
        "role": "system",
        "content": """
You are a Brilliant Data Scientist. You take the following as input:
- The Exploratory Data Analysis (EDA) of a dataset.
- A set of output analyses performed on the dataset.
- A story derived from the dataset based on the analysis.

Your task is to suggest **3 graph types** to enhance the storytelling. 

**Key Instructions**:
- Avoid suggesting heatmaps.
- Output only the names of the graphs, formatted as a bullet-point list.
"""
    },
    {"role": "user", "content": f"The EDA of the dataset:\n{prompt}"},
    {"role": "user", "content": f"Analysis we tried to perform:\n{analysis_to_perform}"},
    {"role": "user", "content": f"The output of the analysis:\n{analysis_output}"},
    {"role": "user", "content": f"The story of the dataset:\n{dataset_story}"},
]


data = {
    "model": "gpt-4o-mini",  # Specify the model
    "messages": chat_history,
    "temperature": 0.5  # Adjust the creativity of the response
}

response = ask_gpt_4o_mini(data)
graph_names = response['choices'][0]['message']["content"]


## GPT for creating graphs
chat_history = [
    {
        "role": "system",
        "content": """
You are a Brilliant Data Scientist. You take the following as input:
- The Exploratory Data Analysis (EDA) of a dataset.
- The names of 3 graphs to be created.

Your task is to output Python code to generate these graphs and save them as PNG files. 

**Key Instructions**:
1. The code should:
   - Save all 3 images in `.png` format.
   - Use the file names `fig1.png`, `fig2.png`, and `fig3.png`.
2. **Code-only Output**: Do not include any explanations or extra text. For example:
   - Input: Code to print hello world
   - Output: `print("hello world")`
3. **Error Handling**:
   - Ensure the code handles errors gracefully using `try-except` blocks.
   - Attempt to access the dataset using UTF-8 encoding first; fallback to Latin-1 if UTF-8 fails.
4. **Graph Readability**:
   - If the axes have many values, focus on the most significant ones to make the graph readable.
"""
    },
    {"role": "user", "content": f"The EDA of the dataset:\n{prompt}"},
    {"role": "user", "content": f"The name of the graphs:\n{graph_names}"},
]

data = {
    "model": "gpt-4o-mini",  # Specify the model
    "messages": chat_history,
    "temperature": 0.7  # Adjust the creativity of the response
}

response = ask_gpt_4o_mini(data)
graph_code = response['choices'][0]['message']["content"]
clean_graph_code = graph_code.replace("`", "").replace("python", "")
exec(clean_graph_code)


## GPT for final story
chat_history = [
        {"role": "system", "content": '''You are a Brilliant Data Scientist, you take EDA of a dataset, a story of the dataset in .md format and the name of 3 graphs saved as fig1.png fig2.png fig3.png and output an enhanced story in .md format with the images used.
        Note: You will output in .md format only. The output you give will be saved as a .md file format.
        '''},
        {"role": "user", "content": "The EDA of the dataset\n" +prompt},
        {"role": "user", "content": "The story of the dataset:\n" + dataset_story},
        {"role": "user", "content": "The name of the graphs saved as fig1.png fig2.png fig3.png:\n" + graph_names},
        ]

data = {
    "model": "gpt-4o-mini",  # Specify the model
    "messages": chat_history,
    "temperature": 0.7  # Adjust the creativity of the response
}

response = ask_gpt_4o_mini(data)
final_story = response['choices'][0]['message']["content"]
clean_final_story = final_story.replace("markdown", "").replace("`", "")

# Saving the story in .md file format
with open("README.md", "w") as f:
  f.write(clean_final_story)
