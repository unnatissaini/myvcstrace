import os
import sys
import hashlib
import pickle
import datetime

VCS_DIR = '.vcs_storage'
COMMITS_FILE = os.path.join(VCS_DIR, 'commits.pkl')

def init_vcs():
    os.makedirs(VCS_DIR, exist_ok=True)
    if not os.path.exists(COMMITS_FILE):
        with open(COMMITS_FILE, 'wb') as f:
            pickle.dump([], f)
    print("✅ VCS initialized.")

def snapshot(directory, message):
    snapshot_hash = hashlib.sha256()
    snapshot_data = {'files': {}, 'message': message}

    for root, _, files in os.walk(directory):
        if VCS_DIR in root:
            continue
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, start=directory)
            with open(full_path, 'rb') as f:
                content = f.read()
                snapshot_hash.update(content)
                snapshot_data['files'][rel_path] = content

    hash_digest = snapshot_hash.hexdigest()
    snapshot_data['file_list'] = list(snapshot_data['files'].keys())

    with open(f'{VCS_DIR}/{hash_digest}', 'wb') as f:
        pickle.dump(snapshot_data, f)

    commit = {
        'hash': hash_digest,
        'message': message,
        'timestamp': datetime.datetime.now().isoformat()
    }

    commits = load_commits()
    commits.append(commit)
    save_commits(commits)

    print(f"📸 Snapshot created with hash: {hash_digest}")

def revert_to_snapshot(hash_digest):
    snapshot_path = os.path.join(VCS_DIR, hash_digest)
    if not os.path.exists(snapshot_path):
        print("❌ Snapshot not found.")
        return

    with open(snapshot_path, 'rb') as f:
        snapshot_data = pickle.load(f)

    for rel_path, content in snapshot_data['files'].items():
        full_path = os.path.join('.', rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(content)

    current_files = set()
    for root, _, files in os.walk('.'):
        if VCS_DIR in root:
            continue
        for file in files:
            full_path = os.path.relpath(os.path.join(root, file), start='.')
            current_files.add(full_path)

    snapshot_files = set(snapshot_data['file_list'])
    for file_to_delete in current_files - snapshot_files:
        os.remove(file_to_delete)
        print(f"🗑️ Removed extra file: {file_to_delete}")

    print(f"⏪ Reverted to snapshot: {hash_digest}")

def show_log():
    commits = load_commits()
    if not commits:
        print("📭 No commits yet.")
        return
    print("📝 Commit Log:")
    for commit in reversed(commits):
        print(f"{commit['hash'][:8]} | {commit['timestamp']} | {commit['message']}")

def load_commits():
    if not os.path.exists(COMMITS_FILE):
        return []
    with open(COMMITS_FILE, 'rb') as f:
        return pickle.load(f)

def save_commits(commits):
    with open(COMMITS_FILE, 'wb') as f:
        pickle.dump(commits, f)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❗Usage: python vcs.py [init | snapshot <msg> | revert <hash> | log]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        init_vcs()
    elif command == "snapshot":
        if len(sys.argv) < 3:
            print("❗Provide a commit message: snapshot <message>")
        else:
            message = ' '.join(sys.argv[2:])
            snapshot('.', message)
    elif command == "revert":
        if len(sys.argv) < 3:
            print("❗Provide a snapshot hash: revert <hash>")
        else:
            revert_to_snapshot(sys.argv[2])
    elif command == "log":
        show_log()
    else:
        print("❌ Unknown command.")
