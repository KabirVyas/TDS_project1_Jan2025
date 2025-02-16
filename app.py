import os
import json
import sqlite3
import subprocess
import numpy as np
import pytesseract
import pandas as pd
import requests
from flask import Flask, request, jsonify, Response
from fastapi import FastAPI, HTTPException, Query
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer, util
from PIL import Image
from dateutil import parser
import calendar
import re
from datetime import datetime
from openpyxl import Workbook
from markdown2 import markdown
import shutil
from dateutil import parser
from fastapi.responses import PlainTextResponse
from pathlib import Path
import csv
import glob
import time
import stat
import duckdb
from bs4 import BeautifulSoup
import whisper

# Load environment variables from .env file
load_dotenv()

# Retrieve AI Proxy Token from environment variables
AIPROXY_TOKEN = os.getenv("AIPROXY_TOKEN")
API_BASE_URL = "https://aiproxy.sanand.workers.dev/openai/v1"

# Ensure the API key is set
if not AIPROXY_TOKEN:
    raise ValueError("Error: AIPROXY_TOKEN is not set. Make sure you have added it to your .env file.")

# Initialize Flask app
app = Flask(__name__)


# Ensure all files are accessed from the 'data' folder inside the project root
PROJECT_ROOT = os.path.abspath(os.getcwd())
DATA_DIR = os.path.join(PROJECT_ROOT, "data")  # ✅ Allowed data directory

# Task mapping for LLM classification
TASK_MAPPING = {
    "install_and_execute": "run_datagen",
    "format_markdown": "format_markdown",
    "count_weekday": "count_weekday",
    "sort_contacts": "sort_contacts",
    "extract_content": "extract_content",
    "extract_headers": "extract_headers",
    "extract_email": "extract_email",
    "extract_credit_card": "extract_credit_card",
    "find_similar_comments": "find_similar_comments",
    "execute_dynamic_query": "execute_dynamic_query"
}

def classify_task(task_description):
    """Use AI Proxy to classify the task correctly."""
    try:
        headers = {
            "Authorization": f"Bearer {AIPROXY_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Classify the task description into EXACTLY one of these labels:\n"
                        + ", ".join(TASK_MAPPING.keys())
                        + ".\n\n"
                        "Return ONLY the exact label, nothing else."
                    )
                },
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(
            "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions",
            headers=headers,
            json=data
        )

        if response.status_code != 200:
            print(f"ERROR: AI Proxy API failed - {response.text}", flush=True)
            return None

        classification = response.json()["choices"][0]["message"]["content"].strip().lower()

        print(f"DEBUG: AI Proxy classified '{task_description}' as '{classification}'", flush=True)

        return classification if classification in TASK_MAPPING else None

    except Exception as e:
        print(f"ERROR: AI Proxy request failed - {e}", flush=True)
        return None

@app.route("/run", methods=["GET", "POST"])
def run_task():
    """Runs a task based on classification."""
    task_description = request.args.get("task")

    if not task_description:
        return jsonify({"error": "Missing task parameter"}), 400

    task_label = classify_task(task_description)

    if not task_label:
        return jsonify({"error": "Task classification failed"}), 500

    if task_label == "install_and_execute":
        return jsonify(run_datagen(task_description)) 

    elif task_label == "format_markdown":
        return format_markdown()  
    
    elif task_label == "count_weekday":
        return count_weekday(task_description)
    
    elif task_label == "sort_contacts":
        return sort_contacts(task_description)
    
    elif task_label == "extract_content":
        return extract_content(task_description)

    elif task_label == "extract_headers":
        return extract_headers(task_description) 

    elif task_label == "extract_email":
        return extract_email(task_description)

    elif task_label == "extract_credit_card":
        return extract_credit_card(task_description)   
    
    elif task_label == "find_similar_comments":
        return find_similar_comments(task_description)
    
    elif task_label == "execute_dynamic_query":
        return execute_dynamic_query(task_description)
    
    elif task_label == "fetch_api_data":
        return fetch_api_data(task_description)
    
    elif task_label == "clone_and_commit_repo":
        return clone_and_commit_repo(task_description)
    
    elif task_label == "run_sql_query":
        return run_sql_query(task_description)
    
    elif task_label == "scrape_website":
        return scrape_website(task_description)
    
    elif task_label == "compress_resize_image":
        return compress_resize_image(task_description)
    
    elif task_label == "transcribe_audio":
        return transcribe_audio(task_description)
    
    elif task_label == "convert_markdown_to_html":
        return convert_markdown_to_html(task_description)
    
    elif task_label == "filter_csv":
        return filter_csv()

    return jsonify({"error": f"Task '{task_label}' is not yet implemented"}), 400

@app.route("/read", methods=["GET", "POST"])
def read_file():
    """Reads a file from the project directory and returns its contents as plain text."""
    relative_path = request.args.get("path")

    if not relative_path:
        return Response("Missing path parameter", status=400, mimetype="text/plain")

    # ✅ Remove leading slash to prevent absolute path issues
    relative_path = relative_path.lstrip("/")

    # ✅ Construct full file path
    file_path = os.path.join(PROJECT_ROOT, relative_path)

    if not os.path.isfile(file_path):
        return Response("File not found", status=404, mimetype="text/plain")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return Response(content, status=200, mimetype="text/plain")  # ✅ Always plain text output
    except Exception as e:
        return Response(f"Failed to read file: {str(e)}", status=500, mimetype="text/plain")

def run_datagen(task_description):
    
    # Extract URL and email from task description
    script_url_match = re.search(r"https?://[^\s]+\.py", task_description)
    user_email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", task_description)

    if not script_url_match or not user_email_match:
        return {"error": "URL or email not found in the prompt."}

    script_url = script_url_match.group(0)
    user_email = user_email_match.group(0)

    script_path = os.path.join(PROJECT_ROOT, "datagen.py")

    try:
        # Download script
        response = requests.get(script_url)
        response.raise_for_status()  # Ensure download was successful
        with open(script_path, "wb") as f:
            f.write(response.content)

        # Check if UV is installed
        try:
            subprocess.run(["uv", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            subprocess.run(["pip", "install", "uv"], check=True)  # Install UV if not found

        # Run the script with user email
        # subprocess.run(["python", script_path, user_email], cwd=PROJECT_ROOT, check=True)
        subprocess.run(["uv", "run", script_url, user_email, "--root", "./data"])
        return {"success": f"Executed {script_url} with email {user_email}"}

    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to download script: {str(e)}"}
    except subprocess.CalledProcessError as e:
        return {"error": f"Command failed: {e}"}

def format_markdown():
    """Format a markdown file using Prettier version 3.4.2."""
    try:
        markdown_file = os.path.join(PROJECT_ROOT, "data", "format.md")

        if not os.path.isfile(markdown_file):
            return jsonify({"error": "format.md not found"}), 404

        print("Executing Prettier formatting...")

        # Ensure Node.js and npx are available
        NPX_PATH = shutil.which("npx")
        if NPX_PATH is None:
            return jsonify({"error": "npx not found. Ensure Node.js is installed and added to PATH."}), 500

        # Run Prettier using npx
        process = subprocess.run(
            f'"{NPX_PATH}" prettier@3.4.2 --write "{markdown_file}"',
            shell=True, capture_output=True, text=True, timeout=30
        )

        # Check if Prettier execution failed
        if process.returncode != 0:
            return jsonify({"error": "Prettier formatting failed", "details": process.stderr}), 500

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Prettier formatting timed out"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    print("Prettier formatting completed successfully.")
    return jsonify({"message": f"Formatted {markdown_file} successfully", "prettier_output": process.stdout}), 200

def count_weekday(task_description):
    """Counts occurrences of a specified weekday from a date file and saves the result."""
    try:
        # ✅ Step 1: Extract Input File, Output File & Weekday from Task Description
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract the weekday, input file path, and output file path from the task description. "
                        "Return in EXACTLY this JSON format: "
                        "{\"weekday\": \"<weekday in English>\", \"input_file\": \"<file path>\", \"output_file\": \"<file path>\"}. "
                        "Example: {\"weekday\": \"Wednesday\", \"input_file\": \"/data/dates.txt\", \"output_file\": \"/data/dates-wednesdays.txt\"}"
                    )
                },
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)

        if response.status_code != 200:
            return jsonify({"error": "LLM extraction failed", "details": response.text}), 500

        # ✅ Step 2: Parse JSON Correctly
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        weekday = extracted_data.get("weekday", "").strip().capitalize()
        input_file = os.path.join(PROJECT_ROOT, extracted_data.get("input_file", "").lstrip("/"))
        output_file = os.path.join(PROJECT_ROOT, extracted_data.get("output_file", "").lstrip("/"))

        # ✅ Ensure valid file names
        if not input_file or not output_file or not weekday:
            return jsonify({"error": "Failed to extract valid details from the prompt."}), 400

        # ✅ Step 3: Ensure the Input File Exists
        if not os.path.exists(input_file):
            return jsonify({"error": f"File '{input_file}' not found"}), 404

        # ✅ Step 4: Read and Parse Dates
        valid_dates = []
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                date_str = line.strip()
                if date_str:
                    try:
                        # ✅ Improve parsing to handle all formats correctly
                        date_obj = parser.parse(date_str, fuzzy=True)
                        valid_dates.append(date_obj)
                    except Exception:
                        continue  # Ignore invalid dates

        # ✅ Step 5: Convert Weekday to Integer (Monday = 0, ..., Sunday = 6)
        weekday_int = list(calendar.day_name).index(weekday)

        # ✅ Step 6: Count Occurrences of the Specified Weekday
        count = sum(1 for date in valid_dates if date.weekday() == weekday_int)

        # ✅ Step 7: Save the Result to the Output File
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(str(count))

        return jsonify({"message": f"{weekday}s counted: {count}", "output_file": output_file}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def sort_contacts(task_description):
    """Dynamically sort contacts.json based on LLM-extracted sorting criteria."""
    try:
        input_file = "data/contacts.json"
        output_file = "data/contacts-sorted.json"
        
        if not os.path.exists(input_file):
            return jsonify({"error": "contacts.json not found"}), 404

        # Load contacts from JSON file
        with open(input_file, "r", encoding="utf-8") as f:
            contacts = json.load(f)

        # Ensure contacts is a list of dictionaries
        if not isinstance(contacts, list) or not all(isinstance(c, dict) for c in contacts):
            return jsonify({"error": "Invalid contacts.json format"}), 500

        # Use LLM to extract sorting criteria
        headers = {
            "Authorization": f"Bearer {AIPROXY_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract sorting criteria from the given task description. "
                        "Return in this exact JSON format: {\"sort_by\": [\"field1\", \"field2\", ...]}."
                    )
                },
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(
            "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions",
            headers=headers,
            json=data
        )

        if response.status_code != 200:
            return jsonify({"error": "LLM extraction failed", "details": response.text}), 500

        # Extract sorting keys from LLM response
        try:
            response_content = response.json()["choices"][0]["message"]["content"]
            extracted_data = json.loads(response_content.strip())  # Properly parse JSON
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON response from LLM", "content": response_content}), 500

        sort_keys = extracted_data.get("sort_by", ["last_name", "first_name"])

        # Sort contacts dynamically, ensuring missing keys are handled correctly
        contacts.sort(key=lambda c: tuple(str(c.get(k, "")).strip().lower() for k in sort_keys))

        # Save the sorted contacts
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(contacts, f, indent=2, ensure_ascii=False)  # Properly formatted output

        return jsonify({"message": "Contacts sorted successfully", "output_file": output_file, "sorted_by": sort_keys}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def extract_content(task_description):
    """Extracts the first line of the N most recent .log files and saves to an output file."""
    try:
        # ✅ Step 1: Extract Input Directory, Output File & Number of Recent Files
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract the log directory, output file, and number of most recent log files from the task description. "
                        "Return in EXACTLY this JSON format: "
                        "{\"log_dir\": \"<directory>\", \"output_file\": \"<file path>\", \"num_files\": <number>}. "
                        "Example: {\"log_dir\": \"/data/logs\", \"output_file\": \"/data/logs-recent.txt\", \"num_files\": 10}"
                    )
                },
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)

        if response.status_code != 200:
            return jsonify({"error": "LLM extraction failed", "details": response.text}), 500

        # ✅ Step 2: Parse JSON Correctly
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        log_dir = os.path.join(PROJECT_ROOT, extracted_data.get("log_dir", "").lstrip("/"))
        output_file = os.path.join(PROJECT_ROOT, extracted_data.get("output_file", "").lstrip("/"))
        num_files = int(extracted_data.get("num_files", 10))  # Default to 10 if missing

        # ✅ Ensure valid file paths & number
        if not log_dir or not output_file or num_files <= 0:
            return jsonify({"error": "Failed to extract valid details from the prompt."}), 400

        # ✅ Step 3: Ensure the Log Directory Exists
        if not os.path.exists(log_dir):
            return jsonify({"error": f"Directory '{log_dir}' not found"}), 404

        # ✅ Step 4: Get Log Files Sorted by Modified Time (Newest First)
        log_files = sorted(
            glob.glob(os.path.join(log_dir, "*.log")),
            key=lambda f: os.path.getmtime(f),  # ✅ Sort by modified time
            reverse=True
        )[:num_files]

        extracted_logs = []

        for file_path in log_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    extracted_logs.append(first_line)  # ✅ Append only first line (without timestamp)
            except Exception:
                extracted_logs.append(f"Error reading {os.path.basename(file_path)}")

        # ✅ Step 5: Save Extracted Data to Output File
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(extracted_logs))

        return jsonify({"message": "Log extraction completed", "output_file": output_file}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_headers(task_description):
    """Finds all Markdown (.md) files (including subdirectories), extracts the first H1 (# Heading), and creates an index JSON file."""
    try:
        # ✅ Step 1: Extract Input Directory & Output File from Task Description
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract the directory containing Markdown files and the output index file from the task description. "
                        "Return in EXACTLY this JSON format: "
                        "{\"input_dir\": \"<directory>\", \"output_file\": \"<file path>\"}. "
                        "Example: {\"input_dir\": \"/data/docs\", \"output_file\": \"/data/docs/index.json\"}"
                    )
                },
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)

        if response.status_code != 200:
            return jsonify({"error": "LLM extraction failed", "details": response.text}), 500

        # ✅ Step 2: Parse JSON Correctly
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        input_dir = os.path.join(PROJECT_ROOT, extracted_data.get("input_dir", "").lstrip("/"))
        output_file = os.path.join(PROJECT_ROOT, extracted_data.get("output_file", "").lstrip("/"))

        # ✅ Ensure valid paths
        if not input_dir or not output_file:
            return jsonify({"error": "Failed to extract valid details from the prompt."}), 400

        # ✅ Step 3: Ensure Input Directory Exists
        if not os.path.exists(input_dir):
            return jsonify({"error": f"Directory '{input_dir}' not found"}), 404

        # ✅ Step 4: Recursively Find All Markdown (.md) Files
        md_files = []
        for root, _, files in os.walk(input_dir):  # ✅ Recursively walk through all subdirectories
            for file in files:
                if file.endswith(".md"):
                    md_files.append(os.path.join(root, file))

        if not md_files:
            return jsonify({"error": "No Markdown files found in the directory or subdirectories"}), 400

        # ✅ Step 5: Extract First H1 from Each File
        index_data = {}

        for file_path in md_files:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("# "):  # ✅ First H1 found
                        # ✅ Convert to relative path with forward slashes
                        relative_path = os.path.relpath(file_path, input_dir).replace("\\", "/")  
                        index_data[relative_path] = line[2:].strip()
                        break  # ✅ Stop reading after first H1

        # ✅ Step 6: Save Index JSON File
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=4)

        return jsonify({"message": "Markdown index created successfully", "output_file": output_file}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def extract_email(task_description):
    """Dynamically process a text file using LLM, correctly extracting input/output file names and processing content."""
    try:
        # ✅ Step 1: Extract Input & Output File Names from Task Description
        headers = {
            "Authorization": f"Bearer {AIPROXY_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract the input file name and output file name from the task description. "
                        "Return ONLY a valid JSON with these exact keys: {\"input_file\": \"<file>\", \"output_file\": \"<file>\"}. "
                        "DO NOT return any extra text or explanations."
                    )
                },
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)

        if response.status_code != 200:
            return jsonify({"error": "LLM request failed", "details": response.text}), 500

        # ✅ Step 2: Parse JSON Correctly
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        input_file = extracted_data.get("input_file", "").strip()
        output_file = extracted_data.get("output_file", "").strip()

        # ✅ Ensure valid file names
        if not input_file or not output_file:
            return jsonify({"error": "Failed to extract file names from the prompt."}), 400

        input_path = os.path.join(PROJECT_ROOT, input_file.lstrip("/"))
        output_path = os.path.join(PROJECT_ROOT, output_file.lstrip("/"))

        # ✅ Step 3: Read File Content
        if not os.path.exists(input_path):
            return jsonify({"error": f"File '{input_file}' not found"}), 404
        
        with open(input_path, "r", encoding="utf-8") as file:
            file_content = file.read()

        # ✅ Step 4: Use Regex to Extract Sender’s Email (Backup Method)
        sender_email_match = re.search(r"From: .*?<(.*?)>", file_content)
        if sender_email_match:
            sender_email = sender_email_match.group(1).strip()
        else:
            sender_email = None  # Use LLM if regex fails

        # ✅ Step 5: If Regex Failed, Ask LLM to Extract Email
        if not sender_email:
            process_data = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Extract only the sender's email address from the email headers."},
                    {"role": "user", "content": f"Extract sender email from:\n\n{file_content}"}
                ]
            }

            process_response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=process_data)

            if process_response.status_code != 200:
                return jsonify({"error": "LLM processing failed", "details": process_response.text}), 500

            sender_email = process_response.json()["choices"][0]["message"]["content"].strip()

        # ✅ Step 6: Save Extracted Email as Plain Text
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(sender_email)

        return {"message": "Task completed", "output_file": output_file}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def extract_credit_card(task_description):
    """Extracts a credit card number from an image and saves it as plain text."""
    try:
        # ✅ Step 1: Use LLM to Extract Input & Output File Names
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract the input file name and output file name from the task description. "
                        "Return ONLY valid JSON with these exact keys: {\"input_file\": \"<file>\", \"output_file\": \"<file>\"}. "
                        "DO NOT include any extra text or explanations."
                    )
                },
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)

        if response.status_code != 200:
            return jsonify({"error": "LLM request failed", "details": response.text}), 500

        # ✅ Step 2: Parse JSON Correctly
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        input_file = extracted_data.get("input_file", "").strip()
        output_file = extracted_data.get("output_file", "").strip()

        # ✅ Ensure valid file names
        if not input_file or not output_file:
            return jsonify({"error": "Failed to extract valid file names from the prompt."}), 400

        input_path = os.path.join(PROJECT_ROOT, input_file.lstrip("/"))
        output_path = os.path.join(PROJECT_ROOT, output_file.lstrip("/"))

        # ✅ Step 3: Check if Image Exists
        if not os.path.exists(input_path):
            return jsonify({"error": f"File '{input_file}' not found"}), 404
        
        # ✅ Step 4: Extract Text from Image Using OCR
        image = Image.open(input_path)
        extracted_text = pytesseract.image_to_string(image)

        # ✅ Step 5: Use Regex to Extract Only the Credit Card Number (Backup Method)
        card_number_match = re.search(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", extracted_text)
        if card_number_match:
            card_number = card_number_match.group(0).replace(" ", "").replace("-", "").strip()  # Remove spaces/hyphens
        else:
            card_number = None  # Use LLM if regex fails

        # ✅ Step 6: If Regex Fails, Ask LLM to Extract Credit Card Number
        if not card_number:
            process_data = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Extract only the credit card number from the given text."},
                    {"role": "user", "content": f"Extract card number from:\n\n{extracted_text}"}
                ]
            }

            process_response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=process_data)

            if process_response.status_code != 200:
                return jsonify({"error": "LLM processing failed", "details": process_response.text}), 500

            card_number = process_response.json()["choices"][0]["message"]["content"].strip()
            card_number = re.sub(r"\D", "", card_number)  # Ensure only digits

        # ✅ Step 7: Save Extracted Card Number as Plain Text
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(card_number)

        return {"message": "Task completed", "output_file": output_file}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ✅ Load the local sentence transformer model
model = SentenceTransformer("all-MiniLM-L6-v2")  # Small, fast, and effective

def find_similar_comments(task_description):
    """Finds the most similar pair of comments using embeddings and writes them to an output file."""
    try:
        # ✅ Step 1: Extract Input & Output File Names from Task Description
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract the input file name and output file name from the task description. "
                        "Return ONLY a valid JSON with these exact keys: {\"input_file\": \"<file>\", \"output_file\": \"<file>\"}. "
                        "DO NOT include any extra text or explanations."
                    )
                },
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post("https://aiproxy.sanand.workers.dev/openai/v1/chat/completions", headers=headers, json=data)

        if response.status_code != 200:
            return jsonify({"error": "LLM request failed", "details": response.text}), 500

        # ✅ Step 2: Parse JSON Correctly
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        input_file = extracted_data.get("input_file", "").strip()
        output_file = extracted_data.get("output_file", "").strip()

        # ✅ Ensure valid file names
        if not input_file or not output_file:
            return jsonify({"error": "Failed to extract valid file names from the prompt."}), 400

        input_path = os.path.join(PROJECT_ROOT, input_file.lstrip("/"))
        output_path = os.path.join(PROJECT_ROOT, output_file.lstrip("/"))

        # ✅ Step 3: Read Comments File
        if not os.path.exists(input_path):
            return jsonify({"error": f"File '{input_file}' not found"}), 404
        
        with open(input_path, "r", encoding="utf-8") as file:
            comments = [line.strip() for line in file.readlines() if line.strip()]

        if len(comments) < 2:
            return jsonify({"error": "Not enough comments to find a similar pair."}), 400

        # ✅ Step 4: Compute Embeddings LOCALLY (No OpenAI API Call)
        embeddings = model.encode(comments, convert_to_tensor=True)

        # ✅ Step 5: Find the Most Similar Pair
        max_sim = -1
        best_pair = ("", "")

        for i in range(len(comments)):
            for j in range(i + 1, len(comments)):
                sim = util.pytorch_cos_sim(embeddings[i], embeddings[j]).item()
                if sim > max_sim:
                    max_sim = sim
                    best_pair = (comments[i], comments[j])

        # ✅ Step 6: Save Most Similar Comments to Output File
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"{best_pair[0]}\n{best_pair[1]}")

        return {"message": "Task completed", "output_file": output_file}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def execute_dynamic_query(task_description):
    """Executes a dynamically generated SQL query on a given SQLite database and saves the result to a file."""
    try:
        # ✅ Step 1: Extract Input File, Output File & SQL Query from Task Description
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Extract the SQLite database file path, output file path, and SQL query from the task description. "
                        "Return in EXACTLY this JSON format: "
                        "{\"input_file\": \"<database file>\", \"output_file\": \"<file path>\", \"query\": \"<SQL query>\"}. "
                        "Example: {\"input_file\": \"/data/ticket-sales.db\", \"output_file\": \"/data/ticket-sales-gold.txt\", "
                        "\"query\": \"SELECT SUM(units * price) FROM tickets WHERE type = 'Gold';\"}"
                    )
                },
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)

        if response.status_code != 200:
            return jsonify({"error": "LLM extraction failed", "details": response.text}), 500

        # ✅ Step 2: Parse JSON Correctly
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        input_file = os.path.join(PROJECT_ROOT, extracted_data.get("input_file", "").lstrip("/"))
        output_file = os.path.join(PROJECT_ROOT, extracted_data.get("output_file", "").lstrip("/"))
        query = extracted_data.get("query", "").strip()

        # ✅ Ensure valid file names & query
        if not input_file or not output_file or not query:
            return jsonify({"error": "Failed to extract valid details from the prompt."}), 400

        # ✅ Step 3: Ensure the Database File Exists
        if not os.path.exists(input_file):
            return jsonify({"error": f"Database file '{input_file}' not found"}), 404

        # ✅ Step 4: Execute SQL Query on SQLite Database
        try:
            with sqlite3.connect(input_file) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                result = cursor.fetchone()
                result_value = result[0] if result and result[0] is not None else 0
        except sqlite3.Error as e:
            return jsonify({"error": f"SQL execution failed: {str(e)}"}), 500

        # ✅ Step 5: Save the Query Result to the Output File
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(str(result_value))

        return {"message": "Task completed", "output_file": output_file}

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

def secure_path(file_path):
    """Ensures the given path is inside /data and prevents directory traversal attacks."""
    abs_path = os.path.abspath(os.path.join(PROJECT_ROOT, file_path.lstrip("/")))
    
    if not abs_path.startswith(DATA_DIR):  
        raise ValueError(f"Access denied: {file_path} is outside the allowed directory.")
    
    return abs_path  # ✅ Safe path inside /data


def fetch_api_data(task_description):
    """Fetches data from an API and saves it to a file, ensuring security constraints."""
    try:
        # ✅ Extract API URL & output file from task description
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Extract the API URL and output file path from the task description."},
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        api_url = extracted_data.get("api_url", "").strip()
        output_file = secure_path(extracted_data.get("output_file", "").strip())  # ✅ Secure path

        if not api_url or not output_file:
            return jsonify({"error": "Invalid API URL or output file"}), 400

        # ✅ Fetch data from API
        api_response = requests.get(api_url)
        api_response.raise_for_status()

        # ✅ Save response to file
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(api_response.text)

        return jsonify({"message": "API data fetched successfully", "output_file": output_file}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def clone_and_commit_repo(task_description):
    """Clones a git repository into /data and makes a commit."""
    try:
        # ✅ Extract repo URL and commit message
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Extract the repo URL, directory name, and commit message from the task description."},
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        repo_url = extracted_data.get("repo_url", "").strip()
        repo_dir = secure_path(f"data/{extracted_data.get('repo_dir', '').strip()}")
        commit_message = extracted_data.get("commit_message", "").strip()

        if not repo_url or not repo_dir or not commit_message:
            return jsonify({"error": "Invalid repo URL, directory, or commit message"}), 400

        # ✅ Clone the repo
        subprocess.run(["git", "clone", repo_url, repo_dir], check=True)

        # ✅ Make a commit
        subprocess.run(["git", "-C", repo_dir, "commit", "--allow-empty", "-m", commit_message], check=True)

        return jsonify({"message": "Repository cloned and committed successfully", "repo_dir": repo_dir}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def run_sql_query(task_description):
    """Executes an SQL query on SQLite or DuckDB and saves the result securely."""
    try:
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Extract the database type, file path, output file, and SQL query."},
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        db_type = extracted_data.get("db_type", "").strip().lower()
        db_path = secure_path(extracted_data.get("db_path", "").strip())  # ✅ Secure path
        output_file = secure_path(extracted_data.get("output_file", "").strip())  # ✅ Secure path
        query = extracted_data.get("query", "").strip()

        if not db_type or not db_path or not output_file or not query:
            return jsonify({"error": "Invalid database type, file path, or query"}), 400

        # ✅ Choose database engine
        if db_type == "sqlite":
            conn = sqlite3.connect(db_path)
        elif db_type == "duckdb":
            conn = duckdb.connect(database=db_path)
        else:
            return jsonify({"error": "Unsupported database type"}), 400

        # ✅ Execute query
        df = pd.read_sql_query(query, conn)
        conn.close()

        # ✅ Save result as CSV
        df.to_csv(output_file, index=False)

        return jsonify({"message": "SQL query executed successfully", "output_file": output_file}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def scrape_website(task_description):
    """Scrapes a website and saves extracted data to a file securely."""
    try:
        # ✅ Extract website URL & output file from task description
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Extract the website URL and output file path from the task description."},
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        website_url = extracted_data.get("website_url", "").strip()
        output_file = secure_path(extracted_data.get("output_file", "").strip())  # ✅ Secure path

        if not website_url or not output_file:
            return jsonify({"error": "Invalid website URL or output file"}), 400

        # ✅ Scrape website content
        response = requests.get(website_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text()

        # ✅ Save extracted text
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(text)

        return jsonify({"message": "Website scraped successfully", "output_file": output_file}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def compress_resize_image(task_description):
    """Compresses or resizes an image and saves it securely."""
    try:
        # ✅ Extract input file, output file, width, and height
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Extract input image, output image, width, and height."},
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        input_file = secure_path(extracted_data.get("input_file", "").strip())  
        output_file = secure_path(extracted_data.get("output_file", "").strip())  
        width = int(extracted_data.get("width", 800))  
        height = int(extracted_data.get("height", 600))  

        if not input_file or not output_file:
            return jsonify({"error": "Invalid input/output file"}), 400

        # ✅ Open & Resize Image
        with Image.open(input_file) as img:
            img = img.resize((width, height))
            img.save(output_file, optimize=True, quality=80)  # ✅ Compress & Save

        return jsonify({"message": "Image resized and compressed successfully", "output_file": output_file}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def transcribe_audio(task_description):
    """Transcribes an MP3 file to text and saves it securely."""
    try:
        # ✅ Extract input file & output file from task description
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Extract input audio file and output transcription file."},
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        input_file = secure_path(extracted_data.get("input_file", "").strip())  
        output_file = secure_path(extracted_data.get("output_file", "").strip())  

        if not input_file or not output_file:
            return jsonify({"error": "Invalid input/output file"}), 400

        # ✅ Transcribe Audio
        model = whisper.load_model("base")
        result = model.transcribe(input_file)

        # ✅ Save transcription
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result["text"])

        return jsonify({"message": "Audio transcribed successfully", "output_file": output_file}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def convert_markdown_to_html(task_description):
    """Converts Markdown to HTML and saves it securely."""
    try:
        # ✅ Extract input file & output file
        headers = {"Authorization": f"Bearer {AIPROXY_TOKEN}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Extract input markdown file and output HTML file."},
                {"role": "user", "content": task_description}
            ]
        }

        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=data)
        extracted_data = json.loads(response.json()["choices"][0]["message"]["content"].strip())

        input_file = secure_path(extracted_data.get("input_file", "").strip())  
        output_file = secure_path(extracted_data.get("output_file", "").strip())  

        if not input_file or not output_file:
            return jsonify({"error": "Invalid input/output file"}), 400

        # ✅ Convert Markdown to HTML
        with open(input_file, "r", encoding="utf-8") as f:
            md_content = f.read()

        html_content = markdown.markdown(md_content)

        # ✅ Save HTML
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        return jsonify({"message": "Markdown converted to HTML successfully", "output_file": output_file}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def filter_csv():
    """Filters a CSV file and returns JSON data based on query parameters."""
    try:
        csv_file = secure_path(request.args.get("file", ""))
        column = request.args.get("column", "")
        value = request.args.get("value", "")

        if not csv_file or not column or not value:
            return jsonify({"error": "Missing parameters"}), 400

        df = pd.read_csv(csv_file)
        filtered_df = df[df[column] == value]

        return jsonify(filtered_df.to_dict(orient="records"))

    except Exception as e:
        return jsonify({"error": str(e)}), 500

 
if __name__ == "__main__":
    app.run(debug=True, port=8000)
