# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pandas",
#     "requests",
#     "matplotlib",
#     "seaborn",
#     "numpy"
# ]
# ///


import sys
import pandas as pd
import os
import requests
import json
import io
import matplotlib
import seaborn
import numpy as np


try:
    file_name = sys.argv[1]

    try:
      df = pd.read_csv(file_name)
    except:
      df = pd.read_csv(file_name, encoding="latin-1")

    api_key = os.environ.get("AIPROXY_TOKEN")
except:
    print("ERROR: check if filename was passed as an argument, if the file is present in the same directory as the script, the file is in .csv format")


# Functions
def ask_gpt_4o_mini(data, count=0):
  url = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
  
  headers = {
      "Content-Type": "application/json",
      "Authorization": f"Bearer {api_key}"
  }

  response = requests.post(url, headers=headers, data=json.dumps(data))
  if response.status_code == 200:
      result = response.json()
      return result
  else:
      if count < 3:
         print("ERROR once")
         ask_gpt_4o_mini(data, count+1)
      else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None


def exec_code(code_string):
  output = io.StringIO()
  sys.stdout = output

  try:
      # Execute the code
      exec(code_string)
  finally:
      # Restore the original stdout
      sys.stdout = sys.__stdout__

  # Get the output as a string
  captured_output = output.getvalue()
  output.close()

  # Print the captured output
  return captured_output

def detect_iqr_outliers(df):
    outliers = {}

    # Iterate over numerical columns to detect outliers
    numerical_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    for col in numerical_cols:
        # Calculate IQR for the column
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        # Identify outliers using the IQR method
        outliers_in_col = df[(df[col] < lower_bound) | (df[col] > upper_bound)]

        # Count and percentage of outliers
        outlier_count = outliers_in_col.shape[0]
        outlier_percentage = (outlier_count / df.shape[0]) * 100

        outliers[col] = {
            'count': outlier_count,
            'percentage': outlier_percentage
        }

    return outliers


def make_prompt(file):
  try:
    df = pd.read_csv(file)
  except:
    df = pd.read_csv(file, encoding="latin-1")

  shape = df.shape
  columns = list(df.columns)
  dtypes = list(df.dtypes.values)
  describe = df.describe()


  # File Name
  file_name = f"Filename: {file}\n"

  # Data Overvew
  data_overview = f'''Data Overview \nshape of the data: {shape[0]} rows and {shape[1]} columns \ncolumns : '''

  for ind in range(len(columns)):
    data_overview += f"'{columns[ind]}' ({dtypes[ind]}), "


  # Descriptive Statistics of Numerical Features
  desc_numerical = f'''\nDescriptive Statistics of numerical features (output of df.describe())  \n{describe}\n'''

  # Descriptive Stats of Categorical Data
  desc_categorical = f'''Descriptive statistics of categorical features  \n'''


  for ind in range(len(columns)):
    col = columns[ind]
    dtype = dtypes[ind]


    if dtype == "object":
      uniq_vals = len(df[col].unique())
      if uniq_vals < 30:

        desc_categorical += f"'{col}': {uniq_vals} unique values (most frequent values) => "

        values = df[col].value_counts().iloc[:5].index
        counts = df[col].value_counts().iloc[:5].values
        for j in range(len(values)):
          desc_categorical += f"('{values[j]}': {counts[j]}), "

      else:
        desc_categorical += f"'{col}': {uniq_vals} unique values"

      desc_categorical += "\n"


  # Null Values
  null_vals = '''Null Values \n'''

  null_cols = df.isna().sum().index
  null_val_count = df.isna().sum().values
  for i in range(len(columns)):
    if null_val_count[i] > 0:
      null_vals += f"'{null_cols[i]}': {null_val_count[i]} null values\n"



  # Outliers
  outliers = detect_iqr_outliers(df)
  outlier_txt = '''Outlier Detection\n'''

  # Print outlier summary
  for col, data in outliers.items():
      count = data['count']
      percentage = data['percentage']
      if count > 0:
          outlier_txt += f"'{col}': {count} outliers detected, comprising {percentage:.2f}% of total values"

      outlier_txt += "\n"


  # Create the prompt
  prompt = file_name + '\n' + data_overview + '\n' + desc_numerical + '\n' + desc_categorical + '\n' + null_vals + '\n' + outlier_txt

  return prompt


prompt = make_prompt(file_name)
with open("README.md", "w") as f:
   f.write(prompt)
## GPT for finding Analysis to perform

chat_history = [
        {"role": "system", "content": '''You are a Brilliant Data Scientist, you take EDA of any dataset as input and offer 5 analysis (avoid correlation anallysis) essential to be performed on this dataset to create a comprehensive story of the data.
        Keep in mind you output only the analysis names, that too in bullet points. eg.) 1. Time Series Analysis'''},
        {"role": "user", "content": prompt},
        ]

data = {
    "model": "gpt-4o-mini",  # Specify the model
    "messages": chat_history,
    "temperature": 0.7  # Adjust the creativity of the response
}

response = ask_gpt_4o_mini(data)
analysis_to_perform = response['choices'][0]['message']["content"]


## GPT for running the analysis
chat_history = [
        {"role": "system", "content": '''You are a Brilliant Data Scientist, you take EDA of any dataset as input and take a list of analysis to perform on the data and write python code to perform the analysis
        Note1: you create code such that there are no image outputs, you create code such that running it using exec() should output the result of all the analysis, ie it should print each and every result
        Note2: you just output code for what is asked you dont talk otherwise. eg.) Input: code to print hello world  Output:print("hello world")
        Note3: The most important NOTE: code cant create any errors, try to take care of that using try, except blocks and keeping the code as simple as possible. Ensure u check you apply numeric analysis to numeric colums only
        Note4: You have to try to access the df with utf first but if it raises error you need to use encoding latin-1
        
        '''},
        {"role": "user", "content": prompt},
        {"role": "user", "content": "analysis to perform:\n" + analysis_to_perform},
        ]

data = {
    "model": "gpt-4o-mini",  # Specify the model
    "messages": chat_history,
    "temperature": 0.7  # Adjust the creativity of the response
}

response = ask_gpt_4o_mini(data)
code = response['choices'][0]['message']["content"]
clean_code = code.replace("`", "").replace("python", "")
print(clean_code)
analysis_output = exec_code(clean_code)


## GPT for creating initial story
chat_history = [
        {"role": "system", "content": '''You are a Brilliant Data Scientist, you take EDA of a dataset, and a set of output analysis performed on it as input and create a story out of it.
        Note1: You can choose to ignore if some result of analysis is not avaliable
        Note2: You create a story of the the dataset explaining about it and give insights.
        Note3: You will output in .md format only. The output you give will be saved as a .md file format
        '''},
        {"role": "user", "content": "The EDA of the dataset\n" +prompt},
        {"role": "user", "content": "analysis we tried to perform perform:\n" + analysis_to_perform},
        {"role": "user", "content": "The output of the analysis:\n" + analysis_output},
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
        {"role": "system", "content": '''You are a Brilliant Data Scientist, you take EDA of a dataset, and a set of output analysis performed on it and a story of the dataset based on the analysis as input and output the name of 3 graphs (avoid heatmaps) we should create to enhance the story.
        Note: Keep in mind you output only the graph names, that too in bullet points.
        '''},
        {"role": "user", "content": "The EDA of the dataset\n" +prompt},
        {"role": "user", "content": "analysis we tried to perform perform:\n" + analysis_to_perform},
        {"role": "user", "content": "The output of the analysis:\n" + analysis_output},
        {"role": "user", "content": "The story of the dataset:\n" + dataset_story},
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
        {"role": "system", "content": '''You are a Brilliant Data Scientist, you take EDA of a dataset, and the name of 3 graphs you need to create, and you output python code to create these 3 graphs and save them as .png
        Note1: you create code such that running it using exec() should save all 3 images in .png format. name of the files fig1.png, fig2.png, fig3.png
        Note2: you just output code for what is asked you dont talk otherwise. eg.) Input: code to print hello world  Output:print("hello world")
        Note3: The most important Note: The code cant create any errors, try to take care of that using try, except blocks
        Note4: Try to make the graph readable if there are many values on x or y axis try to take the most importanats in this case.
        Note5: You have to try to access the df with utf first but if it raises error you need to use encoding latin-1
        '''},
        {"role": "user", "content": "The EDA of the dataset\n" +prompt},
        {"role": "user", "content": "The name of the graphs:\n" + graph_names},
        ]

data = {
    "model": "gpt-4o-mini",  # Specify the model
    "messages": chat_history,
    "temperature": 0.7  # Adjust the creativity of the response
}

response = ask_gpt_4o_mini(data)
graph_code = response['choices'][0]['message']["content"]
clean_graph_code = graph_code.replace("`", "").replace("python", "")
print(clean_graph_code)
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

