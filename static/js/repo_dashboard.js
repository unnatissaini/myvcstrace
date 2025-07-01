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

      // Assign save functionality
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
    body: JSON.stringify({
      filename: filePath,
      content: content
    })
  })
    .then(res => res.json())
    .then(data => {
      if (!data || !data.detail) throw new Error("No response.");
      alert(data.detail || "File saved successfully.");
    })
    .catch(err => alert("Failed to save file: " + err.message));
}

  

  /*function renderFileTree(tree, parent) {
    tree.forEach(item => {
      const li = document.createElement("li");
      li.textContent = item.name;

      if (item.type === "folder") {
        li.classList.add("folder");

        const ul = document.createElement("ul");
        ul.style.display = "none";
        renderFileTree(item.children || [], ul);

        li.onclick = (e) => {
          e.stopPropagation();
          ul.style.display = ul.style.display === "none" ? "block" : "none";
        };

        li.appendChild(ul);
      } else {
        li.classList.add("file");
        const ulCommits = document.createElement("ul");
        ulCommits.style.display = "none";
        li.onclick = (e) => {
          e.stopPropagation();
          viewFile(currentRepoId, item.path);
          // Fetch and toggle commit tree
        if (ulCommits.style.display === "none") {
          fetchAndRenderCommits(currentRepoId, item.path, ulCommits);
          ulCommits.style.display = "block";
        } else {
          ulCommits.style.display = "none";
        }
      };

      li.appendChild(ulCommits);
    }

       fetch(`/repositories/${currentRepoId}/file_commits?file_path=${encodeURIComponent(item.path)}`, {
        headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` }
      })
      .then(res => res.json())
      .then(commits => {
        if (commits.length > 0) {
          const commitList = document.createElement("ul");
          commitList.classList.add("commit-list");
          commits.forEach(commit => {
            const commitLi = document.createElement("li");
            commitLi.textContent = `👤 ${commit.author} — ${commit.message}`;
            commitLi.style.fontSize = "smaller";
            commitLi.style.color = "gray";
            commitList.appendChild(commitLi);
          });
          li.appendChild(commitList);
        }
      })
      .catch(err => console.error("Failed to load commits:", err));
    
      parent.appendChild(li);
    });
  }
*/function renderFileTree(tree, parent) {
  tree.forEach(item => {
    const li = document.createElement("li");
    li.textContent = item.name;

    if (item.type === "folder") {
      li.classList.add("folder");

      const ul = document.createElement("ul");
      ul.style.display = "none";
      renderFileTree(item.children || [], ul);

      li.onclick = (e) => {
        e.stopPropagation();
        ul.style.display = ul.style.display === "none" ? "block" : "none";
      };

      li.appendChild(ul);
    } else {
      li.classList.add("file");

      const ulCommits = document.createElement("ul");
      ulCommits.style.display = "none";

      li.onclick = (e) => {
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
fetch(`/repositories/${currentRepoId}/file_commits?file_path=${encodeURIComponent(item.path)}`, {
        headers: { "Authorization": `Bearer ${localStorage.getItem("token")}` }
      })
      .then(res => res.json())
      .then(commits => {
        if (commits.length > 0) {
          const commitList = document.createElement("ul");
          commitList.classList.add("commit-list");
          commits.forEach(commit => {
            const commitLi = document.createElement("li");
            commitLi.textContent = `👤 ${commit.author} — ${commit.message}`;
            commitLi.style.fontSize = "smaller";
            commitLi.style.color = "gray";
            commitList.appendChild(commitLi);
          });
          li.appendChild(commitList);
        }
      })
      .catch(err => console.error("Failed to load commits:", err));
  function fetchAndRenderCommits(repoId, filePath, ulElement) {
  ulElement.innerHTML = `<li>Loading commits...</li>`;

  const token = localStorage.getItem("token");
  fetch(`/repositories/${repoId}/file_commits?file_path=${encodeURIComponent(filePath)}`, {
    headers: { "Authorization": `Bearer ${token}` }
  })
  .then(res => res.json())
  .then(commits => {
    ulElement.innerHTML = ""; // Clear loading text
    if (commits.length === 0) {
      ulElement.innerHTML = `<li>No commits found</li>`;
      return;
    }

    commits.forEach(commit => {
      const li = document.createElement("li");
      li.innerHTML = `
        <b>${commit.author}</b>: ${commit.message} (${new Date(commit.timestamp).toLocaleString()})
        <button onclick="mergeCommitWithOriginal('${commit.commit_id}', '${filePath}')">Merge</button>
        <button onclick="revertToCommit('${commit.commit_id}')">Revert</button>
      `;
      ulElement.appendChild(li);
    });
  })
  .catch(err => {
    ulElement.innerHTML = `<li>Error loading commits</li>`;
    console.error(err);
  });
}

function mergeCommitWithOriginal(commitId, filename) {
  const formData = new FormData();
  formData.append("commit_id", commitId);
  formData.append("filename", filename);

  const token = localStorage.getItem("token");
  fetch(`/repositories/${currentRepoId}/merge_commit_with_original`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${token}` },
    body: formData
  })
  .then(res => res.json())
  .then(data => alert(data.detail))
  .catch(err => alert("Merge failed: " + err.message));
}
function loadVersions(filename) {
  const token = localStorage.getItem("token");
  fetch(`/repositories/${currentRepoId}/versions?filename=${encodeURIComponent(filename)}`, {
    headers: { "Authorization": `Bearer ${token}` }
  })
  .then(res => res.json())
  .then(versions => {
    const list = document.getElementById("version-list");
    list.innerHTML = "";
    versions.forEach(v => {
      const li = document.createElement("li");
      li.textContent = v.version_file;
      list.appendChild(li);
    });
  })
  .catch(err => alert("Failed to load versions: " + err.message));
}



  function loadFiles(repoId) {
    currentRepoId = repoId;
    const token = localStorage.getItem("token");
  
    // Fetch user's role first
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
          uploadBtn.style.display = ["admin", "editor", "collaborator"].includes(currentRole)
            ? "block" : "none";
        }

  
        // Then load the file tree
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

  };
  

  /*function triggerUpload() {
    actionPanel.classList.add("open");
    document.getElementById("panel-content").innerHTML = `
      <h3>Upload File</h3>
      <input type="file" id="upload-file" />
      <button onclick="submitUpload()">Upload</button>
    `;
  }*/
 function triggerUpload() {
  actionPanel.classList.add("open");

  // Set panel content without button
  const panel = document.getElementById("panel-content");
  panel.innerHTML = `
    <h3>Upload File</h3>
    <input type="file" id="upload-file" />
  `;

  // Create the button dynamically
  const uploadBtn = document.createElement("button");
  uploadBtn.textContent = "Upload";

  // Add event listener
  uploadBtn.addEventListener("click", submitUpload);

  // Append the button
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

  /*function commit(snapshot) {
    actionPanel.classList.add("open");
    document.getElementById("panel-content").innerHTML = `
      <h3>Commit Changes</h3>
      <textarea id="commit-message" placeholder="Enter commit message"></textarea>
      <button onclick="submitCommit(${snapshot})">Commit</button>
    `;
  }*/
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
    const fileContent = fileContentElement.value;
    formData.append("filename", filename);
    formData.append("content", fileContent);  // Send edited content


    const endpoint = snapshot
      ? `/repositories/${currentRepoId}/commit`
      : `/repositories/${currentRepoId}/commit`;

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

  // Create and attach button separately
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

      commits.forEach(commit => {
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
      headers: { "Authorization": `Bearer ${token}` },
    })
      .then(res => {
        if (!res.ok) throw new Error("Revert failed");
        return res.json();
      })
      .then(data => {
        alert(data.message || "Revert successful");
        closeActionPanel();
        viewFile(currentRepoId, filename);  // Reload content in glassy panel
      })
      .catch(err => {
        alert("Error: " + err.message);
      });
  }

  function closeActionPanel() {
    actionPanel.classList.remove("open");
    document.getElementById("panel-content").innerHTML = "";
  }

  async function submitCreateEntry() {
    const name = document.getElementById("new-entry-name").value.trim();
    const token = localStorage.getItem("token");
  
    if (!name) return alert("Name cannot be empty.");
  
    const isFile = name.includes(".");
    const endpoint = isFile ? "create_file" : "create_folder";
  
    const formData = new FormData();
    formData.append("filename", name);  // for folder, same param used
  
    const res = await fetch(`/repositories/${currentRepoId}/${endpoint}`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`
      },
      body: formData,
    });
  
    const data = await res.json();
    if (!res.ok) return alert("Error: " + (data.detail || `Failed to create ${isFile ? 'file' : 'folder'}`));
  
    alert(`${isFile ? 'File' : 'Folder'} created successfully!`);
    closeActionPanel();
    loadFiles(currentRepoId);
  }
  /*function createFile() {
    actionPanel.classList.add("open");
    document.getElementById("panel-content").innerHTML = `
      <h3>Create New File or Folder</h3>
      <input type="text" id="new-entry-name" placeholder="Enter file or folder name" />
      <button onclick="submitCreateEntry()">Create</button>
    `;
  }*/
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

    
  async function submitCreateFile() {
    const filename = document.getElementById("new-filename").value;
    const content = document.getElementById("new-file-content").value;
    const token = localStorage.getItem("token");

    if (!filename) return alert("Filename cannot be empty.");

    const res = await fetch(`/repositories/${currentRepoId}/files`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name: filename, content }),
    });

    const data = await res.json();
    if (!res.ok) return alert("Error: " + (data.detail || "File creation failed"));

    alert("File created!");
    closeActionPanel();
    loadFiles(currentRepoId);
  }

  // Expose to window
  window.triggerUpload = triggerUpload;
  window.commit = commit;
  window.revertFile = revertFile;
  window.closeActionPanel = closeActionPanel;
  window.createFile = createFile;
  window.submitUpload = submitUpload;
  window.submitCommit = submitCommit;
  window.submitRevert = submitRevert;
  window.submitCreateEntry = submitCreateEntry;
  window.submitCreateFile = submitCreateFile;
  window.viewFile = viewFile;
  window.mergeCommitWithOriginal = mergeCommitWithOriginal;
  window.revertToCommit = revertToCommit;



});
