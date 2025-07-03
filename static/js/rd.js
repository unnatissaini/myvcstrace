document.addEventListener('DOMContentLoaded', () => {
  let currentRepoId = null;
  let currentRole = null;
  let CURRENT_FILE_NAME = null;

  const actionPanel = document.getElementById("action-panel");
  const fileNameElement = document.getElementById("file-name");
  const fileContentElement = document.getElementById("file-content");
  const repoId = document.body.getAttribute("data-repo-id");

  if (repoId) {
    loadFiles(repoId);
  }

  // ---------------- File Operations ----------------
  /*function viewFile(repoId, filePath) {
    const ext = filePath.split(".").pop().toLowerCase();
    const viewer = document.getElementById("file-content");
    CURRENT_FILE_NAME = filePath; 
    fileNameElement.textContent = filePath;

    fetch(`/repositories/${repoId}/file?name=${encodeURIComponent(filePath)}`)
      .then(res => res.json())
      .then(data => {
        // For doc, docx, pdf → show editable textarea with commit button
        if (["doc", "docx", "pdf"].includes(ext)) {
          viewer.innerHTML = `
          <textarea id="editor" style="width:100%; height:400px;">${data.content}</textarea>
          <br />
          <button onclick="commitEditedText('${filePath}')">Commit Edited Text</button>
        `;        
        } else {
          // For regular text files
          viewer.innerHTML = `
            <pre style="white-space: pre-wrap; padding: 10px;">${data.content || "(empty)"}</pre>
          `;
        }
      })
      .catch(err => {
        viewer.textContent = "Error loading file.";
        console.error(err);
      });
  }*/
  function viewFile(repoId, filePath) {
    const ext = filePath.split(".").pop().toLowerCase();
    CURRENT_FILE_NAME = filePath;
    fileNameElement.textContent = filePath;
  
    const viewer = document.getElementById("file-content");
  
    fetch(`/repositories/${repoId}/file?name=${encodeURIComponent(filePath)}`)
      .then(res => res.json())
      .then(data => {
        // Display content
        viewer.textContent = data.content || "(empty)";
  
        // Enable buttons
        document.getElementById("edit-btn").style.display =
          ["admin", "editor", "collaborator"].includes(currentRole) ? "inline-block" : "none";
  
        // If versioned file and ends with .txt → allow conversion
        if (filePath.includes("versions/") && filePath.endsWith(".txt")) {
          document.getElementById("convert-btn").style.display = "inline-block";
        } else {
          document.getElementById("convert-btn").style.display = "none";
        }
      })
      .catch(err => {
        viewer.textContent = "Error loading file.";
        console.error(err);
      });
  }
  


function saveFile() {
  const ext = CURRENT_FILE_NAME.split(".").pop().toLowerCase();
  const token = localStorage.getItem("token");

  let contentElement = document.getElementById("editor") || document.getElementById("file-content");

  if (!contentElement) {
    alert("No content to save.");
    return;
  }

  // Get content based on element type
  const content = contentElement.tagName === "TEXTAREA"
    ? contentElement.value
    : contentElement.textContent;

  const confirmMsg = confirm("Are you sure you want to save the current changes?");
  if (!confirmMsg) return;

  fetch(`/repositories/${currentRepoId}/edit_file`, {
    method: "PUT",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      filename: CURRENT_FILE_NAME,
      content: content,
      is_binary: false  // always false since we're editing text
    })
  })
    .then(res => {
      if (!res.ok) throw new Error("Failed to save");
      return res.json();
    })
    .then(data => {
      alert(data.message || "File saved successfully.");
    })
    .catch(err => {
      console.error(err);
      alert("Save failed: " + err.message);
    });
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
      .then(commitTree => {
        ulElement.innerHTML = "";
        if (!commitTree.length) {
          ulElement.innerHTML = `<li>No commits found</li>`;
          return;
        }

        renderCommitTree(commitTree, ulElement, filePath);
      })
      .catch(err => {
        ulElement.innerHTML = `<li>Error loading commits</li>`;
        console.error(err);
      });
  }
  function renderCommitTree(commits, parentUl, filePath) {
    commits.forEach(commit => {
      const li = document.createElement("li");
      li.innerHTML = `
        <div style="margin-left: 8px;">
          <span>#${commit.id} - ${commit.message} [${commit.status}] (${new Date(commit.timestamp).toLocaleString()})</span>
          ${commit.status === "proposed" ? `<button class="merge-btn">Merge</button>` : ""}
        </div>
      `;

      if (commit.status === "proposed") {
        li.querySelector(".merge-btn").addEventListener("click", () => {
          mergeCommitWithOriginal(commit.id, filePath);
        });
      }

      li.addEventListener("click", (e) => {
        e.stopPropagation();
        viewCommitFile(commit.id);
      });

      parentUl.appendChild(li);

      // Recursively add children commits if any
      if (commit.children && commit.children.length > 0) {
        const nestedUl = document.createElement("ul");
        nestedUl.style.marginLeft = "20px";
        li.appendChild(nestedUl);
        renderCommitTree(commit.children, nestedUl, filePath);
      }
    });
  }

  function viewCommitFile(commitId) {
    const token = localStorage.getItem("token");
  
    fetch(`/repositories/${currentRepoId}/commit_preview/${commitId}`, {
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(res => {
        if (!res.ok) throw new Error("Failed to load commit preview");
        return res.json();
      })
      .then(data => {
        fileNameElement.textContent = `Commit #${commitId} → ${data.filename}`;
        fileContentElement.textContent = data.content;
  
        // Disable editing controls
        document.getElementById("edit-btn").style.display = "none";
        document.getElementById("convert-btn").style.display = "none";
        document.getElementById("save-file-btn").style.display = "none";
      })
      .catch(err => {
        alert("Error loading commit: " + err.message);
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
    const filename = CURRENT_FILE_NAME;
    if (!message) return alert("Enter a commit message.");
    if (filename === "Select a file") return alert("Select a file first.");

    const token = localStorage.getItem("token");
    const formData = new FormData();
    formData.append("message", message);
    formData.append("filename", filename);
    const editor = document.getElementById("editor");
    const content = editor ? editor.value : fileContentElement.textContent || "";
    formData.append("content", content);
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
    const filename = CURRENT_FILE_NAME;
    const panel = document.getElementById("action-panel");
    const content = document.getElementById("panel-content");
    panel.classList.add("open");
  
    const token = localStorage.getItem("token");
  
    // 🔁 1. Handle trash restore if no file selected
    if (!filename || filename === "Select a file") {
      fetch(`/repositories/${currentRepoId}/trash_files`, {
        headers: { "Authorization": `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(files => {
          if (!files.length) {
            content.innerHTML = `<p>No deleted files found in trash.</p>`;
            return;
          }
  
          content.innerHTML = `
            <h3>Restore Deleted File</h3>
            <select id="restore-file-select" style="width:100%; padding: 5px;">
              ${files.map(f => `<option value="${f}">${f}</option>`).join("")}
            </select>
            <br><br>
            <button onclick="submitRestore()">Restore Selected File</button>
          `;
        })
        .catch(err => {
          content.innerHTML = `<p>Error loading trash files.</p>`;
          console.error(err);
        });
  
      return;
    }
  
    // 🧠 2. If file is selected, check if it's a merged version
    fetch(`/repositories/${currentRepoId}/file_merge_info?file_name=${encodeURIComponent(filename)}`, {
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(info => {
        if (info.is_merged) {
          const confirmMsg = `This file was created by merging:\n• ${info.sources.join("\n• ")}\n\nAre you sure you want to undo this merge?`;
          if (!confirm(confirmMsg)) return;
  
          return fetch(`/repositories/${currentRepoId}/revert/${info.commit_id}`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${token}` }
          });
        } else {
          // ❗ If not a merged file and revert of normal commits is disabled, show warning
          alert("This file was not created via merge and cannot be reverted.");
          closeActionPanel();
          return;
        }
      })
      .then(res => {
        if (!res) return;
        return res.json();
      })
      .then(data => {
        if (data) {
          alert(data.message || "Revert successful");
          closeActionPanel();
          viewFile(currentRepoId, filename);
        }
      })
      .catch(err => {
        console.error("Revert failed", err);
        alert("Error: " + err.message);
      });
  }
    
  function submitRestore() {
    const selectedFile = document.getElementById("restore-file-select").value;
    const token = localStorage.getItem("token");
  
    fetch(`/repositories/${currentRepoId}/revert_deleted?filename=${encodeURIComponent(selectedFile)}`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        alert(data.message || "File restored.");
        closeActionPanel();
        loadFiles(currentRepoId);
      })
      .catch(err => {
        alert("Restore failed: " + err.message);
      });
  }
  
    
  function submitRevert() {
    const filename = CURRENT_FILE_NAME;
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

function mergeCommitWithOriginal(commitId, filePath) {
  if (!commitId || commitId === "undefined" || isNaN(commitId)) {
    alert("Invalid commit ID — merge aborted.");
    return;
  }

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
  function submitGenericMerge() {
    const repoId = document.body.getAttribute("data-repo-id");
    const selectedFiles = Array.from(
      document.querySelectorAll('#merge-version-list input[type="checkbox"]:checked')
    ).map(cb => cb.value);
  
    if (selectedFiles.length !== 2) {
      alert("Select exactly 2 version files to merge.");
      return;
    }
  
    const token = localStorage.getItem("token");
  
    fetch(`/repositories/${repoId}/merge_versions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify({ version_files: selectedFiles })
    })
      .then(res => res.json())
      .then(data => {
        alert(data.message || "Version merge complete.");
        closeActionPanel();
        loadFiles(repoId);
      })
      .catch(err => {
        console.error("Merge failed:", err);
        alert("Failed to merge versions.");
      });
  }
  
  function mergeFile() {
    const repoId = document.body.getAttribute("data-repo-id");
    const fileName = document.getElementById("file-name").innerText;
    const panel = document.getElementById("action-panel");
    const content = document.getElementById("panel-content");
    panel.classList.add("open");
  
    // If no file is selected, show option to select from all version files
    if (fileName === "Select a file") {
      content.innerHTML = `<h3>Merge Any Two Versions</h3><p>Select version files to merge:</p><div id="merge-version-list">Loading...</div><button onclick="submitGenericMerge()">Merge Selected</button>`;
  
      fetch(`/repositories/${repoId}/version_files`, {
        headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` }
      })
        .then(res => res.json())
        .then(files => {
          const listDiv = document.getElementById("merge-version-list");
          listDiv.innerHTML = files
            .filter(f => f.endsWith(".txt"))
            .map(f => `<label><input type="checkbox" value="${f}"> ${f}</label><br>`)
            .join("");
        })
        .catch(err => {
          document.getElementById("merge-version-list").innerHTML = "Failed to load version files.";
          console.error(err);
        });
  
      return;
    }
  
    // If a file is selected, merge its commits
    fetch(`/repositories/${repoId}/file_commits?file_path=${encodeURIComponent(fileName)}`)
      .then(res => res.json())
      .then(commits => {
        if (!commits || commits.length === 0) {
          content.innerHTML = `<p>No commits found for this file.</p>`;
          return;
        }
  
        content.innerHTML = `
          <h3>Merge Commits for ${fileName}</h3>
          <div>Select commits to merge:</div>
          <div style="max-height:150px; overflow-y:auto;">
            ${commits
              .filter(c => c.status === "proposed")
              .map(
                c =>
                  `<label><input type="checkbox" value="${c.commit_id}"> Commit ${c.commit_id}: ${c.message}</label><br>`
              )
              .join("")}
          </div>
          <button onclick="confirmMerge('${fileName}', ${repoId})">Confirm Merge</button>
        `;
      });
  }
  
  function confirmMerge(fileName, repoId) {
    const selectedCommits = Array.from(
      document.querySelectorAll('#panel-content input[type="checkbox"]:checked')
    ).map(cb => cb.value);
  
    if (selectedCommits.length < 2) {
      alert("Select at least 2 commits to merge.");
      return;
    }
  
    const token = localStorage.getItem("token");
  
    // Send `null` if no actual file is selected (e.g., when merging version files)
    const payload = {
      file_name: fileName === "Select a file" ? null : fileName,
      commit_ids: selectedCommits
    };
  
    fetch(`/repositories/${repoId}/merge`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    })
      .then(res => {
        if (!res.ok) throw new Error("Merge failed");
        return res.json();
      })
      .then(data => {
        alert(data.message || `Merge completed into ${data.versioned_filename}`);
        closeActionPanel();
        loadFiles(repoId);
      })
      .catch(err => {
        console.error("Merge error:", err);
        alert("Merge failed: " + err.message);
      });
  }
  
  
  function startEditingFile() {
    const token = localStorage.getItem("token");
  
    fetch(`/repositories/${currentRepoId}/edit_file_text?name=${encodeURIComponent(CURRENT_FILE_NAME)}`, {
      headers: { "Authorization": `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        // Update current file to .txt version for commits
        CURRENT_FILE_NAME = data.editable_path;
  
        const viewer = document.getElementById("file-content");
        viewer.innerHTML = `
          <textarea id="editor" style="width:100%; height:400px;">${data.content}</textarea>
          <br>
          <button onclick="commitEditedText('${data.editable_path}')">Commit Edited Text</button>
        `;
      })
      .catch(err => {
        alert("Error preparing file for editing: " + err.message);
      });
  }
  
  
  function showConvertOptions() {
    const panel = document.getElementById("action-panel");
    const content = document.getElementById("panel-content");
    panel.classList.add("open");
  
    content.innerHTML = `
      <h3>Convert Version File</h3>
      <p>File: ${CURRENT_FILE_NAME}</p>
      <select id="target-format">
        <option value="docx">DOCX</option>
        <option value="pdf">PDF</option>
        <option value="doc">DOC</option>
      </select>
      <br><br>
      <button onclick="convertFile()">Convert & Download</button>
    `;
  }
  
  function convertFile() {
    const format = document.getElementById("target-format").value;
    const url = `/repositories/${currentRepoId}/convert_version?filename=${encodeURIComponent(CURRENT_FILE_NAME)}&target_format=${format}`;
  
    window.open(url, "_blank"); // Trigger file download
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
  window.startEditingFile = startEditingFile;
  window.showConvertOptions = showConvertOptions;
  window.convertFile = convertFile;
  window.submitRestore = submitRestore;
  window.submitGenericMerge = submitGenericMerge;

});
