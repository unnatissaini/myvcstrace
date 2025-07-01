    // Data container
    let dashboardData = null;
    let currentRepoId = null;

    // Cache DOM elements
    const contentBox = document.getElementById('content-box');
    const navItems = document.querySelectorAll('.nav-item');
    const createRepoPanel = document.getElementById('create-repo-panel');
    const closeCreateBtn = document.getElementById('close-create-panel');
    function openCreateRepoPanel() {
    createRepoPanel.classList.add('open');
    document.body.classList.add('panel-open'); // add class
    createRepoPanel.setAttribute('aria-hidden', 'false');
    }

    function closeCreateRepoPanel() {
    createRepoPanel.classList.remove('open');
    document.body.classList.remove('panel-open'); // remove class
    createRepoPanel.setAttribute('aria-hidden', 'true');
    }

    // Fetch dashboard data once on load
    async function fetchDashboardData() {
      const token = localStorage.getItem("token");
      if (!token) {
        window.location.href = "/login";
        return;
      }

      try {
        const res = await fetch("/api/dashboard-data", {
          headers: { "Authorization": `Bearer ${token}` }
        });

        if (!res.ok) {
          localStorage.removeItem("token");
          window.location.href = "/login";
          return;
        }

        const data = await res.json();
        dashboardData = data;
        renderSection('home'); // Show home on load
      } catch (err) {
        console.error("Dashboard error:", err);
        contentBox.innerHTML = "<p>Error loading dashboard data.</p>";
      }
    }

    // Render content based on section
    function renderSection(section) {
      clearActiveNav();
      document.querySelector(`.nav-item[data-section="${section}"]`).classList.add('active');

      if (!dashboardData) {
        contentBox.innerHTML = "<p>Loading...</p>";
        return;
      }

      switch (section) {
        case 'home':
          renderHome();
          break;
        case 'report':
          renderRepos();
          break;
        case 'activity':
          renderActivity();
          break;
        default:
          contentBox.innerHTML = "<p>Section not found.</p>";
      }
    }

    function clearActiveNav() {
      navItems.forEach(i => i.classList.remove('active'));
    }

    // Home content
    function renderHome() {
      closeCreateRepoPanel(); // Close panel if open
      const user = dashboardData.user;
      const repoCount = dashboardData.repos.length;

      contentBox.innerHTML = `
        <h3>Welcome, <span id="username">${user.username}</span></h3>
        <p id="user-id">User ID: ${user.id}</p>
        <p id="repo-count">Total Repositories: ${repoCount}</p>
        <button id="btn-create-repo" style="
          margin-top: 1.5rem;
          padding: 0.7rem 1.2rem;
          font-size: 1rem;
          font-weight: 600;
          border-radius: 10px;
          border: none;
          cursor: pointer;
          background: #81a1c1;
          color: #121619;
          transition: background-color 0.3s ease;
        ">Create New Repository</button>
      `;

      document.getElementById('btn-create-repo').addEventListener('click', openCreateRepoPanel);
    }

    // Render Repos table
    function renderRepos() {
      closeCreateRepoPanel();
      const repos = dashboardData.repos;

      let repoSectionHTML = `
  <h3>Your Repositories</h3>
`;

if (!repos.length) {
  repoSectionHTML += `<p>You have not created any repositories yet.</p>`;
} else {
  let rows = '';
  repos.forEach(repo => {
    rows += `
      <tr>
        <td><a href="#" onclick="openRepoDashboard(${repo.id})">${repo.name}</a></td>
        <td>${repo.visibility}</td>
        <td>${repo.created_at}</td>
        <td>
          <button class="action-btn" onclick="openAccessPanel(${repo.id})">Access</button>
          <button class="action-btn" onclick="deleteRepo(${repo.id})">Delete</button>
          <button class="action-btn" onclick="snapshotRepo(${repo.id})">Snapshot</button>
        </td>
      </tr>
    `;
  });

  repoSectionHTML += `
    <table id="repo-table">
      <thead>
        <tr>
          <th>Name</th><th>Visibility</th><th>Created</th><th>Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  contentBox.innerHTML = repoSectionHTML;
}


      let rows = '';
      repos.forEach(repo => {
        rows += `
          <tr>
            <td><a href="#" onclick="openRepoDashboard(${repo.id})">${repo.name}</a>            
            <td>${repo.visibility}</td>
            <td>${repo.created_at}</td>
            <td>
              <button class="action-btn" onclick="openAccessPanel(${repo.id})">Access</button>
              <button class="action-btn" onclick="deleteRepo(${repo.id})">Delete</button>
              <button class="action-btn" onclick="snapshotRepo(${repo.id})">Snapshot</button>
            </td>
          </tr>
        `;
        document.getElementById("access-form").addEventListener("submit", updateAccessControl);
      });

      contentBox.innerHTML = `
        <h3>Your Repositories</h3>
        <table id="repo-table">
          <thead>
            <tr>
              <th>Name</th><th>Visibility</th><th>Created</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
        <h3>Accessible Repositories</h3>
        <table id="accessible-repos">
          <thead>
            <tr>
              <th>Name</th>
              <th>Owner</th>
              <th>Visibility</th>
              <th>Role</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>

        <!-- Upload Section -->
        <div id="upload-section" style="display:none; margin-top: 2rem;">
          <h4>Upload File</h4>
          <form id="upload-form">
            <input type="file" id="file-upload" name="file" required />
            <button type="submit">Upload</button>
          </form>
        </div>

        <!-- Commit Section -->
        <div id="commit-section" style="display:none; margin-top: 2rem;">
          <h4>Commit Changes</h4>
          <form id="commit-form">
            <input type="text" name="message" placeholder="Commit message" required />
            <input type="text" name="filename" placeholder="File name" required />
            <label><input type="checkbox" name="create_snapshot" checked /> Create Snapshot</label>
            <button type="submit">Commit</button>
          </form>
        </div>

        <div id="access-section" style="display:none; margin-top: 2rem;">
          <h4>Add Collaborator</h4>
          <form id="access-form">
            <input name="user_id" placeholder="User ID" required />
            <select name="role">
              <option value="viewer">Viewer</option>
              <option value="collaborator">Collaborator</option>
              <option value="admin">Admin</option>
            </select>
            <button type="submit">Update</button>
          </form>
        </div>
      `;
      loadAccessibleRepos();
      // Add event listeners to forms after rendering
      document.getElementById("upload-form").addEventListener("submit", uploadFile);
      document.getElementById("commit-form").addEventListener("submit", commitChanges);
      document.getElementById("access-form").addEventListener("submit", updateAccessControl);
    }
    document.getElementById("access-form").addEventListener("submit", updateAccessControl);
    // Activity log rendering
    function renderActivity() {
      closeCreateRepoPanel();
      const logs = dashboardData.logs;

      if (!logs.length) {
        contentBox.innerHTML = `<p>No activity logs available.</p>`;
        return;
      }

      let listItems = '';
      logs.forEach(log => {
        listItems += `<li>${log.timestamp}: ${log.action} on repo ${log.repo_id}</li>`;
      });

      contentBox.innerHTML = `
        <h3>Recent Activity</h3>
        <ul id="log-list">${listItems}</ul>
      `;
    }
    function openRepoDashboard(repoId) {
      const token = localStorage.getItem("token");
      if (!token) {
        alert("Please log in");
        return window.location.href = "/login";
      }
    
      const form = document.createElement("form");
      form.method = "POST";
      form.action = `/repositories/${repoId}/open`;
      form.target = "_blank";
    
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "token";
      input.value = token;
      form.appendChild(input);
    
      document.body.appendChild(form);
      form.submit();
      document.body.removeChild(form);
    }
    window.openRepoDashboard = openRepoDashboard;

    
    
    function openRepository(repoId) {
      const token = localStorage.getItem("token");
      if (!token) return alert("Login required");
    
      window.location.href = `/repositories/${repoId}/dashboard?token=${token}`;
    }
    let currentFileName = null; 
      async function renderRepoView(repoId, repoName, role) {
        currentRepoId = repoId;

        const token = localStorage.getItem("token");
        contentBox.innerHTML = `<h3>Loading repository...</h3>`;

        try {
          const res = await fetch(`/repositories/${repoId}/files`, {
            headers: { Authorization: `Bearer ${token}` },
          });

          if (!res.ok) throw new Error("Failed to fetch files");

          const files = await res.json();

          let fileItems = files.map(file => `
            <li onclick="loadFileContent('${file}')">${file}</li>
          `).join("");

          const isEditor = role === "collaborator" || role === "editor" || role === "admin" || role === "owner";

          const buttonsHTML = isEditor ? `
            <button onclick="triggerUpload()">Upload</button>
            <button onclick="triggerCreateFile()">Create File</button>
            <button onclick="commitFile(true)">Commit (Snapshot)</button>
            <button onclick="commitFile(false)">Commit (No Snapshot)</button>
            <button onclick="triggerRevert()">Revert</button>
          ` : `<p><em>You have viewer access. Editing is disabled.</em></p>`;

          contentBox.innerHTML = `
            <div class="repo-view">
              <h3>Repository: ${repoName}</h3>
              <div class="repo-controls">
                ${buttonsHTML}
              </div>

              <div class="file-list">
                <h4>Files</h4>
                <ul id="file-list">${fileItems}</ul>
              </div>

              <div class="file-content">
                <h4>File Content</h4>
                <pre id="file-content-box">Select a file to view its content...</pre>
                ${isEditor ? `<button id="save-file-btn">Save Changes</button>` : ""}              
              </div>
            </div>
          `;
          if (isEditor) {
            document.getElementById("save-file-btn").addEventListener("click", () => {
              if (!currentFileName) {
                alert("No file selected");
                return;
              }
              const content = document.getElementById("file-content-box").value;
              saveFile(currentRepoId, currentFileName, content);
            });
          }
        } catch (err) {
          console.error(err);
          contentBox.innerHTML = "<p>Error loading repository files.</p>";
        }
      }

      
      // Load file content
      async function loadFileContent(filename) {
        const token = localStorage.getItem("token");
      
        try {
          const res = await fetch(`/repositories/${currentRepoId}/file?name=${encodeURIComponent(filename)}`, {
            headers: { Authorization: `Bearer ${token}` }
          });
      
          if (!res.ok) throw new Error("Failed to load file");
      
          const data = await res.json();
          document.getElementById("file-content-box").textContent = data.content;
        } catch (err) {
          console.error(err);
          document.getElementById("file-content-box").textContent = "Error loading file.";
        }
      }

      function triggerUpload() {
        alert("Upload modal or panel will open.");
      }
      function triggerCreateFile() {
        alert("Create new file modal will open.");
      }
      function commitFile(withSnapshot) {
        alert("Committing file with snapshot: " + withSnapshot);
      }
      function triggerRevert() {
        alert("Revert file will be triggered.");
      }
      
    closeCreateBtn.addEventListener('click', closeCreateRepoPanel);

    // Create repo form submit
    document.getElementById('create-repo-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const token = localStorage.getItem("token");
      if (!token) return window.location.href = "/login";

      const form = e.target;
      const formData = new FormData();
      formData.append("name", form.name.value);
      formData.append("is_private", String(form.visibility.value === "private"));
      formData.append("description", ""); 

      const fileInput = form.querySelector("#repo-file");  // ✅ correct input reference
      if (fileInput.files.length > 0) {
        formData.append("file", fileInput.files[0]);
      }

      try {
  const res = await fetch("/repositories/create", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`
    },
    body: formData
  });

  const data = await res.json();

  if (!res.ok) {
    console.error("💥 Backend error:", data);
    alert(JSON.stringify(data.detail || data, null, 2)); // 👈 this will be readable
    return;
  }

  alert(`Repository '${data.repo_name}' created successfully!`);
  closeCreateRepoPanel();
  await fetchDashboardData();
} catch (err) {
  console.error("❌ JS fetch failed:", err);
  alert("Client-side error: " + err.message);
}

/*      try {
        const res = await fetch("/repositories/create", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`
          },
          body: formData
        });

        const data = await res.json();

        if (!res.ok) {
          alert(data.detail || "Failed to create repository.");
          return;
        }

        alert(`Repository '${data.repo_name}' created successfully!`);
        closeCreateRepoPanel();
        await fetchDashboardData(); // Refresh UI
      } catch (err) {
        console.error("Repo creation failed:", err);
        alert("Failed to create repository.");
      }
      const data = await res.json();
      console.error("Error details:", data); // ✅ see what FastAPI says

      if (!res.ok) {
        alert(data.detail || "Failed to create repository.");
        return;
      }
*/
    });

    // Delete repo
    async function deleteRepo(repoId) {
      if (!confirm("Are you sure you want to delete this repository?")) return;
      const token = localStorage.getItem("token");
      try {
        const res = await fetch(`/repositories/${repoId}`, {
          method: "DELETE",
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        const data = await res.json();
        alert(data.detail || "Repository deleted");
        await fetchDashboardData();
      } catch (err) {
        console.error(err);
        alert("Failed to delete repository.");
      }
    }

    // Snapshot repo
    async function snapshotRepo(repoId) {
      const token = localStorage.getItem("token");
      try {
        const res = await fetch(`/repositories/${repoId}/snapshot_repo`, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        const data = await res.json();
        alert("Snapshot created: " + data.snapshot_id);
      } catch (err) {
        console.error(err);
        alert("Failed to create snapshot.");
      }
    }

    // Upload file
    async function uploadFile(e) {
      e.preventDefault();
      if (!currentRepoId) return alert("Select a repository first.");
      const token = localStorage.getItem("token");
      const formData = new FormData();
      const fileInput = document.getElementById("file-upload");
      if (!fileInput.files[0]) return alert("Choose a file to upload.");
      formData.append("file", fileInput.files[0]);

      try {
        const res = await fetch(`/repositories/${currentRepoId}/upload`, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`
          },
          body: formData
        });
        const data = await res.json();
        alert("Uploaded: " + data.file_uploaded);
      } catch (err) {
        console.error(err);
        alert("Upload failed.");
      }
    }

    // Commit changes
    async function commitChanges(e) {
      e.preventDefault();
      if (!currentRepoId) return alert("Select a repository first.");

      const token = localStorage.getItem("token");
      const form = e.target;
      const formData = new FormData(form);
      const message = formData.get("message");
      const filename = formData.get("filename");
      //const createSnapshot = form.create_snapshot.checked;

      const endpoint = `/repositories/${currentRepoId}/commit`;


      const finalForm = new FormData();
      finalForm.append("message", message);
      finalForm.append("filename", filename);

      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`
          },
          body: finalForm
        });
        const data = await res.json();
        alert(data.message || "Commit successful");
      } catch (err) {
        console.error(err);
        alert("Failed to commit.");
      }
    }

    // Update access control
    async function updateAccessControl(e) {
      e.preventDefault();
      if (!currentRepoId) return alert("Select a repository first.");

      const token = localStorage.getItem("token");
      const formData = new FormData(e.target);
      try {
        const res = await fetch(`/repositories/${currentRepoId}/access-control`, {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${token}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            user_id: Number(formData.get("user_id")),
            role: formData.get("role")
          })
        });
        console.log("Granting access to repo:", currentRepoId);
        const data = await res.json();
        alert(data.detail);
      } catch (err) {
        console.error(err);
        alert("Failed to update access.");
      }
      console.log("Sending access:", {
  user_id: Number(formData.get("user_id")),
  role: formData.get("role")
  
});

    }

    const accessRepoPanel = document.getElementById("access-repo-panel");
    const closeAccessBtn = document.getElementById("close-access-panel");
    async function openAccessPanel(repoId) {
        currentRepoId = repoId;
        accessRepoPanel.classList.add("open");
        accessRepoPanel.setAttribute("aria-hidden", "false");
        document.body.classList.add("panel-open");
        }
    
    async function closeAccessPanel() {
        accessRepoPanel.classList.remove("open");
        accessRepoPanel.setAttribute("aria-hidden", "true");
        document.body.classList.remove("panel-open");
        }
    // Navigation click handling
    navItems.forEach(item => {
      item.addEventListener('click', () => {
        const section = item.getAttribute('data-section');
        renderSection(section);
      });
    });

    // Initial fetch
    fetchDashboardData();

    // Expose functions for inline handlers in repo table buttons
    
    window.deleteRepo = deleteRepo;
    window.snapshotRepo = snapshotRepo;

    closeAccessBtn.addEventListener("click", closeAccessPanel);
    window.openAccessPanel = openAccessPanel;
    
    async function loadAccessibleRepos() {
      const token = localStorage.getItem("token");
      const res = await fetch("/accessible-repositories", {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      const repos = await res.json();
      const tbody = document.querySelector("#accessible-repos tbody");
      tbody.innerHTML = "";
    
      for (const repo of repos) {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>
            
            <a href="#" onclick="openRepoDashboard(${ repo.id })">${ repo.name }</a>
          </td>
          <td>${repo.owner}</td>
          <td>${repo.visibility}</td>
          <td>${repo.role}</td>          
        `;
        tbody.appendChild(row);
      }
    }

    