document.addEventListener('DOMContentLoaded', () => {
  let currentRepoId = null;
  let currentRole = null;

  const actionPanel = document.getElementById("action-panel");
  const fileNameElement = document.getElementById("file-name");
  const fileContentElement = document.getElementById("file-content");
  const repoId = document.body.getAttribute("data-repo-id");

  if (repoId) {
    loadFiles(repoId);
  }

  // ---------------- File Operations ----------------

  function viewFile(repoId, filePath) {
    const token = localStorage.getItem("token");
    fileNameElement.textContent = filePath;

    fetch(`/repositories/${repoId}/file?name=${encodeURIComponent(filePath)}`, {
      headers: { "Authorization": `Bearer ${token}` },
    })
      .then(res => res.json())
      .then(data => {
        fileContentElement.value = data.content;
        const editableRoles = ["admin", "editor", "collaborator"];
        const canEdit = editableRoles.includes(currentRole);

        fileContentElement.readOnly = !canEdit;
        document.getElementById("save-file-btn").style.display = canEdit ? "inline-block" : "none";

        if (canEdit) {
          document.getElementById("save-file-btn").onclick = () => {
            saveFile(repoId, filePath, fileContentElement.value);
          };
        }
      })
      .catch(err => alert("Error: " + err.message));
  }

  function saveFile(repoId, filePath, content) {
    const token = localStorage.getItem("token");
    fetch(`/repositories/${repoId}/edit_file`, {
      method: "PUT",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ filename: filePath, content: content })
    })
      .then(res => res.json())
      .then(data => {
        if (!data || !data.detail) throw new Error("No response.");
        alert(data.detail || "File saved successfully.");
      })
      .catch(err => alert("Failed to save file: " + err.message));
  }

  // ---------------- File Tree ----------------

  function renderFileTree(tree, parent) {
    tree.forEach(item => {
      const li = document.createElement("li");
      li.textContent = item.name;

      if (item.type === "folder") {
        li.classList.add("folder");
        const ul = document.createElement("ul");
        ul.style.display = "none";
        renderFileTree(item.children || [], ul);

        li.onclick = e => {
          e.stopPropagation();
          ul.style.display = ul.style.display === "none" ? "block" : "none";
        };

        li.appendChild(ul);
      } else {
        li.classList.add("file");
        const ulCommits = document.createElement("ul");
        ulCommits.style.display = "none";

        li.onclick = e => {
          e.stopPropagation();
          viewFile(currentRepoId, item.path);
          if (ulCommits.style.display === "none") {
            fetchAndRenderCommits(currentRepoId, item.path, ulCommits);
            ulCommits.style.display = "block";
          } else {
            ulCommits.style.display = "none";
          }
        };

        li.appendChild(ulCommits);
      }

      parent.appendChild(li);
    });
  }

  function fetchAndRenderCommits(repoId, filePath, ulElement) {
    ulElement.innerHTML = `<li>Loading commits...</li>`;
    const token = localStorage.getItem("token");
    
    fetch(`/repositories/${repoId}/file_commits?file_path=${encodeURIComponent(filePath)}`, {
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(commits => {
        ulElement.innerHTML = "";
        if (commits.length === 0) {
          ulElement.innerHTML = `<li>No commits found</li>`;
          return;
        }
        commits.filter(c => c.status !== "merged").forEach(commit => {
          const li = document.createElement("li");
          li.innerHTML = `
            <div>
              #${commit.commit_id} - ${commit.message} [${commit.status}] (${new Date(commit.timestamp).toLocaleString()})
              <button class="merge-btn">Merge</button>
            </div>
          `;
        
          li.querySelector(".merge-btn").addEventListener("click", () => {
            mergeCommitWithOriginal(commit.commit_id, filePath);
          });
        
          li.addEventListener("click", (e) => {
            e.stopPropagation(); // Avoid toggling parent file list
            viewCommitFile(commit.commit_id);
          });
        
          ulElement.appendChild(li);
        });        
      })
      .catch(err => {
        ulElement.innerHTML = `<li>Error loading commits</li>`;
        console.error(err);
      });
  }

  function viewCommitFile(commitId) {
      const token = localStorage.getItem("token");
    
      fetch(`/repositories/${currentRepoId}/commit_file?commit_id=${commitId}`, {
        headers: { "Authorization": `Bearer ${token}` }
      })
        .then(res => {
          if (!res.ok) throw new Error("Failed to load commit file");
          return res.json();
        })
        .then(data => {
          fileNameElement.textContent = `Commit #${commitId}`;
          fileContentElement.value = data.content;
          fileContentElement.readOnly = true;
          document.getElementById("save-file-btn").style.display = "none";
        })
        .catch(err => {
          alert("Error loading commit file: " + err.message);
        });
    }
    
    function deleteFile() {
    const fileName = document.getElementById("file-name").textContent;
    if (fileName === "Select a file") {
        alert("Please select a file to delete.");
        return;
    }

    if (!confirm(`Are you sure you want to delete "${fileName}"?`)) {
        return;
    }

    const repoId = currentRepoId;  // Make sure currentRepoId is set when repo is selected
    const token = localStorage.getItem("token");
    const filePath = fileName;

    fetch(`/repositories/${repoId}/file`, {
        method: "DELETE",
        headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ file_path: filePath })
    })
    .then(res => {
        if (!res.ok) throw new Error("Failed to delete file.");
        return res.json();
    })
    .then(data => {
        alert(data.detail || "File deleted successfully.");
        fileNameElement.textContent = "Select a file";
        fileContentElement.value = "";
        // Optionally, refresh file list or UI
    })
    .catch(err => {
        alert(`Error: ${err.message}`);
    });
    }


  // ---------------- Upload ----------------

  function triggerUpload() {
    actionPanel.classList.add("open");
    const panel = document.getElementById("panel-content");
    panel.innerHTML = `
      <h3>Upload File</h3>
      <input type="file" id="upload-file" />
    `;
    const uploadBtn = document.createElement("button");
    uploadBtn.textContent = "Upload";
    uploadBtn.addEventListener("click", submitUpload);
    panel.appendChild(uploadBtn);
  }

  function submitUpload() {
    const fileInput = document.getElementById("upload-file");
    const file = fileInput.files[0];
    if (!file) return alert("Choose a file to upload.");

    const formData = new FormData();
    formData.append("file", file);
    const token = localStorage.getItem("token");

    fetch(`/repositories/${currentRepoId}/upload`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` },
      body: formData,
    })
      .then(res => res.json())
      .then(() => {
        alert("File uploaded successfully!");
        closeActionPanel();
        loadFiles(currentRepoId);
      });
  }

  // ---------------- Commit ----------------

  function commit(snapshot) {
    actionPanel.classList.add("open");
    const panel = document.getElementById("panel-content");
    panel.innerHTML = `
      <h3>Commit Changes</h3>
      <textarea id="commit-message" placeholder="Enter commit message"></textarea>
    `;
    const commitBtn = document.createElement("button");
    commitBtn.textContent = "Commit";
    commitBtn.addEventListener("click", () => submitCommit(snapshot));
    panel.appendChild(commitBtn);
  }

  function submitCommit(snapshot) {
    const message = document.getElementById("commit-message").value;
    const filename = fileNameElement.textContent;
    if (!message) return alert("Enter a commit message.");
    if (filename === "Select a file") return alert("Select a file first.");

    const token = localStorage.getItem("token");
    const formData = new FormData();
    formData.append("message", message);
    formData.append("filename", filename);
    formData.append("content", fileContentElement.value);
    formData.append("create_snapshot", snapshot);

    const endpoint = `/repositories/${currentRepoId}/commit`;

    fetch(endpoint, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` },
      body: formData,
    })
      .then(res => res.json())
      .then(data => {
        alert(data.message);
        closeActionPanel();
      });
  }

  // ---------------- Revert ----------------

  function revertFile() {
    const filename = fileNameElement.textContent;
    if (!filename || filename === "Select a file") {
      return alert("Select a file first to revert.");
    }

    actionPanel.classList.add("open");
    const panel = document.getElementById("panel-content");
    panel.innerHTML = `
      <h3>Revert File</h3>
      <p>File: <b>${filename}</b></p>
      <select id="revert-commit-id" style="width: 100%; padding: 5px;">
        <option value="">Loading commits...</option>
      </select>
    `;
    const revertBtn = document.createElement("button");
    revertBtn.textContent = "Revert to Commit";
    revertBtn.addEventListener("click", submitRevert);
    panel.appendChild(revertBtn);

    const token = localStorage.getItem("token");
    fetch(`/repositories/${currentRepoId}/file_commits?file_path=${encodeURIComponent(filename)}`, {
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(commits => {
        const dropdown = document.getElementById("revert-commit-id");
        dropdown.innerHTML = "";
        if (commits.length === 0) {
          dropdown.innerHTML = `<option value="">No snapshots found for this file.</option>`;
          return;
        }
        commits.filter(c => c.status !== "merged").forEach(commit => {
          const option = document.createElement("option");
          option.value = commit.commit_id;
          option.textContent = `#${commit.commit_id} - ${commit.message} (${new Date(commit.timestamp).toLocaleString()})`;
          dropdown.appendChild(option);
        });
      })
      .catch(err => {
        document.getElementById("revert-commit-id").innerHTML = `<option>Error loading commits</option>`;
        console.error(err);
      });
  }

  function submitRevert() {
    const filename = fileNameElement.textContent;
    const commitId = document.getElementById("revert-commit-id").value;
    const token = localStorage.getItem("token");

    if (!commitId) return alert("Please enter a commit ID.");

    fetch(`/repositories/${currentRepoId}/revert/${commitId}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(res => {
        if (!res.ok) throw new Error("Revert failed");
        return res.json();
      })
      .then(data => {
        alert(data.message || "Revert successful");
        closeActionPanel();
        viewFile(currentRepoId, filename);
      })
      .catch(err => alert("Error: " + err.message));
  }

  // ---------------- Helpers ----------------

  function mergeCommitWithOriginal(commitId, filename) {
    const token = localStorage.getItem("token");
  
    fetch(`/repositories/${currentRepoId}/merge/${commitId}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => alert(data.message || "Merged successfully."))
      .catch(err => alert("Merge failed: " + err.message));
  }
  

  function closeActionPanel() {
    actionPanel.classList.remove("open");
    document.getElementById("panel-content").innerHTML = "";
  }

  function loadFiles(repoId) {
    currentRepoId = repoId;
    const token = localStorage.getItem("token");

    fetch(`/repositories/${repoId}/role`, {
      headers: { "Authorization": `Bearer ${token}` },
    })
      .then(res => {
        if (!res.ok) throw new Error("Failed to fetch role");
        return res.json();
      })
      .then(roleData => {
        currentRole = roleData.role;
        console.log("User role:", currentRole);

        const uploadBtn = document.getElementById("upload-button");
        if (uploadBtn) {
          uploadBtn.style.display = ["admin", "editor", "collaborator"].includes(currentRole) ? "block" : "none";
        }

        return fetch(`/repositories/${repoId}/files`, {
          headers: { "Authorization": `Bearer ${token}` },
        });
      })
      .then(res => res.json())
      .then(tree => {
        const listPanel = document.getElementById("file-list");
        listPanel.innerHTML = "";
        renderFileTree(tree, listPanel);
      })
      .catch(err => alert("Error loading repository: " + err.message));
  }

  function createFile() {
    actionPanel.classList.add("open");
    const panel = document.getElementById("panel-content");
    panel.innerHTML = `
      <h3>Create New File or Folder</h3>
      <input type="text" id="new-entry-name" placeholder="Enter file or folder name" />
    `;
    const createBtn = document.createElement("button");
    createBtn.textContent = "Create";
    createBtn.addEventListener("click", submitCreateEntry);
    panel.appendChild(createBtn);
  }

  async function submitCreateEntry() {
    const name = document.getElementById("new-entry-name").value.trim();
    const token = localStorage.getItem("token");
    if (!name) return alert("Name cannot be empty.");

    const isFile = name.includes(".");
    const endpoint = isFile ? "create_file" : "create_folder";

    const formData = new FormData();
    formData.append("filename", name);

    const res = await fetch(`/repositories/${currentRepoId}/${endpoint}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` },
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) return alert("Error: " + (data.detail || `Failed to create ${isFile ? 'file' : 'folder'}`));

    alert(`${isFile ? 'File' : 'Folder'} created successfully!`);
    closeActionPanel();
    loadFiles(currentRepoId);
  }
  function mergeFile() {
    const repoId = document.body.getAttribute("data-repo-id");
    const fileName = document.getElementById("file-name").innerText;
    if (fileName === "Select a file") {
      alert("Select a file first!");
      return;
    }
  
    const panel = document.getElementById("action-panel");
    const content = document.getElementById("panel-content");
    panel.classList.add("open");

    fetch(`/repositories/${repoId}/file_commits?file_path=${encodeURIComponent(fileName)}`)
      .then(res => res.json())
      .then(commits => {
        if (!commits || commits.length === 0) {
          console.log("Commits API response", commits);
          content.innerHTML = `<p>No commits found for this file.</p>`;
          return;
        }
  
        content.innerHTML = `
          <h3>Merge Commits for ${fileName}</h3>
          <div>Select commits to merge:</div>
          <div style="max-height:150px; overflow-y:auto;">
            ${commits.map(c => 
              `<label><input type="checkbox" value="${c.commit_id}"> Commit ${c.commit_id}: ${c.message}</label><br>`
            ).join("")}
          </div>
          <button onclick="confirmMerge('${fileName}', ${repoId})">Confirm Merge</button>
        `;
      });
  }
  
  function confirmMerge(fileName, repoId) {
    const selectedCommits = Array.from(document.querySelectorAll('#panel-content input[type="checkbox"]:checked'))
      .map(cb => cb.value);
  
    if (selectedCommits.length < 2) {
      alert("Select at least 2 commits to merge.");
      return;
    }
  
    const token = localStorage.getItem("token");
    fetch(`/repositories/${repoId}/merge`, {
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({
        file_name: fileName,
        commit_ids: selectedCommits
      })
    }).then(res => res.json())
      .then(data => {
        alert(data.message || `Merge completed into ${data.versioned_filename}`);
        closeActionPanel();
        loadFiles(repoId);
      })
      
      .catch(err => alert("Merge failed: " + err.message));
  }
  
  
  // Expose globally
  window.loadFiles = loadFiles;
  window.triggerUpload = triggerUpload;
  window.submitUpload = submitUpload;
  window.commit = commit;
  window.submitCommit = submitCommit;
  window.revertFile = revertFile;
  window.submitRevert = submitRevert;
  window.mergeCommitWithOriginal = mergeCommitWithOriginal;
  window.closeActionPanel = closeActionPanel;
  window.createFile = createFile;
  window.submitCreateEntry = submitCreateEntry;
  window.viewFile = viewFile;
  window.deleteFile = deleteFile;
  window.mergeFile = mergeFile;
  window.confirmMerge = confirmMerge;
});
