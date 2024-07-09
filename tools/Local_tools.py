import os


def get_folder_structure():
    current_dir = os.getcwd()
    target_folders = ["files/pdfs", "files/markdowns"]
    folder_structure = {}
    for target_folder in target_folders:
        folder_path = os.path.join(current_dir, target_folder)
        if os.path.exists(folder_path):
            files = [os.path.splitext(file)[0] for file in os.listdir(folder_path)]
            folder_structure[target_folder] = {"files": files}
    return folder_structure
