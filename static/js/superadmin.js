// static/js/superadmin.js

// Load a section dynamically into the glassy box

async function loadSection(clickedItem, sectionName) {
  // Highlight selected nav item
  document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
  clickedItem.classList.add("active");

  try {
    const res = await fetch(`/superadmin/section/${sectionName}`);
    if (!res.ok) throw new Error("Failed to load section");
    const html = await res.text();
    document.getElementById("main-display").innerHTML = html;

    // Initialize after content is inserted
    if (sectionName === "overview") init_overview();
    else if (sectionName === "users") init_users();
    else if (sectionName === "repositories") init_repositories();
    else if (sectionName === 'logs') {setTimeout(loadLogs, 300); }
    else if (sectionName === "register") initRegisterForm();
    else if (sectionName === 'reset_password') initResetPasswordPanel();

  } catch (err) {
    document.getElementById("main-display").innerHTML = `<p>Error loading section: ${err.message}</p>`;
  }
}


// Handle logout
function logout() {
  document.cookie = "superadmin_logged_in=; Max-Age=0";
  window.location.href = "/superadmin-login";
}
function init_overview() {
  fetch("/api/superadmin/stats")
    .then(res => {
      if (!res.ok) throw new Error("Failed to fetch stats");
      return res.json();
    })
    .then(data => {
      document.getElementById("total-users").textContent = data.total_users;
      document.getElementById("total-repos").textContent = data.total_repos;
      document.getElementById("public-repos").textContent = data.public_repos;
      document.getElementById("private-repos").textContent = data.private_repos;
    })
    .catch(err => {
      console.error("Error:", err);
    });
}
function init_users() {
  fetch("/api/superadmin/users")
    .then(res => res.json())
    .then(users => {
      const tbody = document.getElementById("user-table-body");
      tbody.innerHTML = "";
      users.forEach(user => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${user.id}</td>
          <td>${user.username}</td>
          <td>
            <button class="action-btn" onclick="deleteUser(${user.id})">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    })
    .catch(err => console.error("Failed to load users:", err));
}

function deleteUser(userId) {
  if (!confirm("Are you sure you want to delete this user?")) return;

  fetch(`/api/superadmin/users/${userId}`, {
    method: "DELETE"
  })
    .then(res => {
      if (!res.ok) throw new Error("Delete failed");
      init_users(); // Refresh list
    })
    .catch(err => alert("Error: " + err.message));
}
function init_repositories() {
  fetch("/api/superadmin/repositories")
    .then(res => res.json())
    .then(repos => {
      const tbody = document.getElementById("repo-table-body");
      tbody.innerHTML = "";
      repos.forEach(repo => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${repo.id}</td>
          <td>
            <a href="#" onclick="openAsAdmin(${repo.id})">${repo.name}</a>
          </td>
          <td>${repo.owner_username}</td>
          <td>${repo.visibility}</td>
          <td>
            <button class="action-btn" onclick="toggleRepo(${repo.id})">Toggle Visibility</button>
            <button class="action-btn" onclick="deleteRepo(${repo.id})">Delete</button>
          </td>
        `;
        tbody.appendChild(tr);
      });
    })
    .catch(err => console.error("Error loading repos:", err));
}
function openAsAdmin(repoId) {
  window.location.href = `/superadmin/repo/${repoId}/dashboard`;
}

function toggleRepo(repoId) {
  fetch(`/api/superadmin/repositories/${repoId}/toggle`, {
    method: "POST"
  })
    .then(res => {
      if (!res.ok) throw new Error("Toggle failed");
      init_repositories(); // Refresh
    })
    .catch(err => alert("Error: " + err.message));
}

function deleteRepo(repoId) {
  if (!confirm("Delete this repository?")) return;

  fetch(`/api/superadmin/repositories/${repoId}`, {
    method: "DELETE"
  })
    .then(res => {
      if (!res.ok) throw new Error("Delete failed");
      init_repositories();
    })
    .catch(err => alert("Error: " + err.message));
}

async function loadAllLogs() {
  const res = await fetch("/api/superadmin/logs");
  const logs = await res.json();
  renderLogs(logs);
}

async function loadUserLogs(userId) {
  const res = await fetch(`/api/superadmin/logs/user/${userId}`);
  const logs = await res.json();
  renderLogs(logs);
}

async function loadRepoLogs(repoId) {
  const res = await fetch(`/api/superadmin/logs/repo/${repoId}`);
  const logs = await res.json();
  renderLogs(logs);
}

function renderLogs(logs) {
  const list = document.getElementById("log-list");
  list.innerHTML = "";

  logs.forEach(log => {
    const li = document.createElement("li");
    li.innerHTML = `
      <strong>Action:</strong> ${log.action} <br>
      <strong>User:</strong> <a href="#" onclick="loadUserLogs(${log.user_id})">${log.user_id}</a><br>
      <strong>Repo:</strong> <a href="#" onclick="loadRepoLogs(${log.repo_id})">${log.repo_id}</a><br>
      <strong>Time:</strong> ${new Date(log.timestamp).toLocaleString()}
    `;
    list.appendChild(li);
  });
}
async function loadLogs() {
  const userList = document.getElementById("user-list");
  const repoList = document.getElementById("repo-list");
  const logTable = document.getElementById("log-table-body");
  const logTitle = document.getElementById("log-title");

  // Load Users
  const users = await (await fetch("/api/superadmin/users-list")).json();
  userList.innerHTML = "";
  users.forEach(user => {
    const li = document.createElement("li");
    li.innerText = `${user.username} (${user.id})`;
    li.onclick = () => fetchLogsByUser(user.id, user.username);
    userList.appendChild(li);
  });

  // Load Repos
  const repos = await (await fetch("/api/superadmin/repos-list")).json();
  repoList.innerHTML = "";
  repos.forEach(repo => {
    const li = document.createElement("li");
    li.innerText = `${repo.name} (${repo.id})`;
    li.onclick = () => fetchLogsByRepo(repo.id, repo.name);
    repoList.appendChild(li);
  });

  async function fetchLogsByUser(userId, username) {
    const logs = await (await fetch(`/api/superadmin/logs/user/${userId}`)).json();
    logTitle.innerText = `Logs for User: ${username}`;
    renderLogTable(logs);
  }

  async function fetchLogsByRepo(repoId, repoName) {
    const logs = await (await fetch(`/api/superadmin/logs/repo/${repoId}`)).json();
    logTitle.innerText = `Logs for Repository: ${repoName}`;
    renderLogTable(logs);
  }

  function renderLogTable(logs) {
    logTable.innerHTML = "";
    if (!logs.length) {
      logTable.innerHTML = "<tr><td colspan='4'>No logs found.</td></tr>";
      return;
    }

    logs.forEach(log => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${log.user_id}</td>
        <td>${log.repo_id}</td>
        <td>${log.action}</td>
        <td>${new Date(log.timestamp).toLocaleString()}</td>
      `;
      logTable.appendChild(row);
    });
  }
}

window.loadLogs = loadLogs;
function initRegisterForm() {
  const form = document.getElementById("register-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(form);
    const payload = {
      username: formData.get("username"),
      password: formData.get("password")
    };

    try {
      const res = await fetch("/auth/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      document.getElementById("register-result").innerText = data.message || "Registered Already!";
    } catch (err) {
      document.getElementById("register-result").innerText = "Error registering user";
    }
  });
}
function initResetPasswordPanel() {
  const form = document.getElementById("reset-password-form");
  const userSelect = document.getElementById("user-select");
  const resetStatus = document.getElementById("reset-status");

  if (!form || !userSelect) return;

  // Load users into the select dropdown
  fetch("/api/superadmin/users")
    .then(res => res.json())
    .then(users => {
      userSelect.innerHTML = users
        .map(user => `<option value="${user.id}">${user.username} (ID: ${user.id})</option>`)
        .join('');
    })
    .catch(err => {
      userSelect.innerHTML = `<option>Error loading users</option>`;
      console.error("Failed to fetch users for reset password:", err);
    });

  // Handle password reset form submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const userId = userSelect.value;
    const newPassword = document.getElementById("new-password").value;

    const formData = new FormData();
    formData.append("new_password", newPassword);

    try {
      const res = await fetch(`/api/superadmin/reset-password/${userId}`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      resetStatus.innerText = data.message || "Password reset successful!";
    } catch (err) {
      resetStatus.innerText = "Error resetting password.";
      console.error("Reset password failed:", err);
    }
  });
}

// On page load: trigger default section
document.addEventListener("DOMContentLoaded", () => {
  document.querySelector(".nav-item.active")?.click();
});
