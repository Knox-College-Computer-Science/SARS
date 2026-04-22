from fastapi import UploadFile
import os

upload_folder = "RAG_Uploads"

def save_uploaded_file(file: UploadFile):
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    file_path = os.path.join(upload_folder, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())
    file_dict = {
        "file_path": file_path,
        "file_name": file.filename
    }

    return file_dict

