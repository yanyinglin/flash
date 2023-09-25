#!/usr/bin/env python
from flask import Flask, request, jsonify
from waitress import serve
import os,time
import torch

with torch.inference_mode():
    if os.environ.get('infer_device') is None:
        infer_device = ('cuda' if torch.cuda.is_available() else 'cpu')
        os.environ['infer_device'] = infer_device
    if os.environ.get('infer_device') == 'cuda' and not torch.cuda.is_available():
        os.environ['infer_device'] = 'cpu'

    infer_device = os.environ.get('infer_device')
    model= torch.load('/mnt/model/gss/{function_model_name}.pt').to(infer_device)

app = Flask(__name__)

class Event:
    def __init__(self):
        self.body = request.get_data()
        self.headers = request.headers
        self.method = request.method
        self.query = request.args
        self.path = request.path

class Context:
    def __init__(self):
        self.hostname = os.getenv('HOSTNAME', 'localhost')

def format_status_code(res):
    if 'statusCode' in res:
        return res['statusCode']
    
    return 200

def format_body(res, content_type):
    if content_type == 'application/octet-stream':
        return res['body']

    if 'body' not in res:
        return ""
    elif type(res['body']) == dict:
        return jsonify(res['body'])
    else:
        return str(res['body'])

def format_headers(res):
    if 'headers' not in res:
        return []
    elif type(res['headers']) == dict:
        headers = []
        for key in res['headers'].keys():
            header_tuple = (key, res['headers'][key])
            headers.append(header_tuple)
        return headers
    
    return res['headers']

def get_content_type(res):
    content_type = ""
    if 'headers' in res:
        content_type = res['headers'].get('Content-type', '')
    return content_type

def format_response(res):
    if res == None:
        return ('', 200)

    statusCode = format_status_code(res)
    content_type = get_content_type(res)
    body = format_body(res, content_type)

    headers = format_headers(res)

    return (body, statusCode, headers)

@app.route('/', defaults={'path': ''}, methods=['GET', 'PUT', 'POST', 'PATCH', 'DELETE'])
@app.route('/<path:path>', methods=['GET', 'PUT', 'POST', 'PATCH', 'DELETE'])
def call_handler(path):
    start_time = time.time()
    event = Event()
    context = Context()
    # event = ""
    # context = ""
    res = {}
    with torch.inference_mode():
        x= {function_input_x}
        output = model(x)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    end_time = time.time()
    res = {"start_time": start_time,"end_time":end_time,"infer_device": infer_device, "exec_time": end_time - start_time}
    res = format_response(res)
    {call_sub_graph}
    return res

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
