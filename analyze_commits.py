import git
import os
import pandas as pd
import re

# =================CONFIGURATION=================
target_dir = r"F:\Reengineering\ardu_pilot_mission_planner" 
csv_path = r"F:\Reengineering\bug_fixing_commit_hashes.csv"
output_csv_path = r"F:\Reengineering\bug_fixing_with_szz_and_ml.csv"
# ===============================================

ML_LIBRARIES = [
    "tensorflow", "torch", "torchvision", "torchaudio", "keras",
    "sklearn", "scikit", "xgboost", "lightgbm", "catboost", "onnx",
    "jax", "paddle", "fastai", "transformers", "datasets",
    "huggingface", "cv2", "mediapipe", "detectron2",
    "stable_diffusion", "sentence_transformers"
]

def is_ml_file(repo, commit_hash, file_path):
    """
    Checks if a file in a specific commit is a Python file and contains ML library mentions.
    """
    if not file_path.endswith('.py'):
        return False
    
    try:
        # Get file content at that specific commit
        content = repo.git.show(f"{commit_hash}:{file_path}")
        content_lower = content.lower()
        for lib in ML_LIBRARIES:
            if lib.lower() in content_lower:
                return True
    except:
        pass
    return False

def analyze_commits():
    try:
        repo = git.Repo(target_dir)
        print(f"Repository '{target_dir}' loaded successfully.")
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        print(f"Error: '{target_dir}' is not a valid Git repository.")
        return

    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
        
    try:
        df = pd.read_csv(csv_path)
        if 'commit_hash' not in df.columns:
            print("Error: Column 'commit_hash' not found in CSV.")
            return
        
        # New columns
        df['originating_file'] = None
        df['is_ml_origin'] = False
        df['bug_introducing_commit'] = None

        print(f"Processing {len(df)} rows...")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    for index, row in df.iterrows():
        target_hash = row['commit_hash'].strip()
        
        try:
            commit = repo.commit(target_hash)
            if not commit.parents:
                continue
                
            parent_hash = commit.parents[0].hexsha
            raw_diff_output = repo.git.show(target_hash)
            
            # --- Identify Buggy Line & File ---
            diff_lines = raw_diff_output.splitlines()
            current_file = None
            current_old_line_number = 0
            buggy_file = None
            buggy_line_num = None

            for line in diff_lines:
                if line.startswith('--- a/') and not line.startswith('--- a/dev/null'):
                    current_file = line[len('--- a/'):].strip()
                if line.startswith('@@ -'):
                    match = re.match(r'@@ -(\d+),?(\d*) \+\d+,?(\d*) @@', line)
                    if match:
                        current_old_line_number = int(match.group(1)) - 1
                if current_file and line.startswith('-') and not line.startswith('---'):
                    buggy_file = current_file
                    buggy_line_num = current_old_line_number + 1
                    break
                if current_file and not line.startswith('+'):
                    current_old_line_number += 1

            if buggy_file and buggy_line_num:
                # --- SZZ: Find Introducing Commit ---
                try:
                    blame_output = repo.git.blame(parent_hash, '--', buggy_file, L=f'{buggy_line_num},{buggy_line_num}')
                    intro_commit = blame_output.split(' ')[0]
                    
                    # Update DataFrame
                    df.at[index, 'originating_file'] = buggy_file
                    df.at[index, 'bug_introducing_commit'] = intro_commit
                    
                    # --- ML Check: Check the file at the introducing commit ---
                    df.at[index, 'is_ml_origin'] = is_ml_file(repo, intro_commit, buggy_file)
                except Exception as e:
                    pass

        except Exception as e:
            print(f"Error processing commit {target_hash}: {e}")

        if (index + 1) % 50 == 0:
            print(f"Processed {index + 1}/{len(df)} rows...")

    # Save the updated CSV
    df.to_csv(output_csv_path, index=False)
    print(f"\nAnalysis complete! Results saved to '{output_csv_path}'.")

if __name__ == "__main__":
    analyze_commits()
