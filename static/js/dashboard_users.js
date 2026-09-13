/**
 * dashboard_users.js - Controlador Frontend para la Gestión de Usuarios Remotos y Permisos Multi-Tenant.
 */

let cachedRagBases = [];
let cachedUsersMap = new Map();

document.addEventListener("DOMContentLoaded", () => {
    const btnUsers = document.getElementById("btn-users");
    if (btnUsers) {
        btnUsers.addEventListener("click", () => {
            loadUsers();
        });
    }
});

/**
 * Obtiene la lista de bases LanceDB disponibles para poblar los selectores de permisos.
 */
async function fetchAvailableRagBases() {
    try {
        const response = await fetch("/api/rag/bases");
        if (response.ok) {
            const data = await response.json();
            cachedRagBases = data.bases || [];
        }
    } catch (err) {
        console.error("Error al obtener bases RAG para administración de usuarios:", err);
    }
}

/**
 * Renderiza checkboxes para cada base RAG disponible en el contenedor indicado.
 */
function renderRagCheckboxes(containerId, selectedTables = []) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!cachedRagBases || cachedRagBases.length === 0) {
        container.innerHTML = `
            <div class="p-2 text-slate-400 text-[11px] italic">
                Cargando o no se detectaron bases LanceDB...
            </div>
        `;
        return;
    }

    const isAll = selectedTables.includes("*");
    container.innerHTML = cachedRagBases.map(b => {
        const tbl = b.table_name;
        const isChecked = isAll || selectedTables.includes(tbl) || (selectedTables.length === 0 && b.is_default);
        const displayName = b.display_name || b.empresa || tbl;
        const defaultTag = b.is_default ? '<span class="text-[9px] px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 font-mono">Predeterminada</span>' : '';

        return `
            <label class="flex items-center gap-2 p-1.5 rounded-lg hover:bg-slate-900 cursor-pointer select-none transition-colors">
                <input type="checkbox" value="${escapeHtml(tbl)}" ${isChecked ? 'checked' : ''} class="w-3.5 h-3.5 rounded bg-slate-950 border-slate-600 text-brand focus:ring-brand/20">
                <div class="flex-1 flex items-center justify-between">
                    <span class="text-slate-200 font-medium">${escapeHtml(displayName)}</span>
                    ${defaultTag}
                </div>
            </label>
        `;
    }).join("");
}

function onNewUserRoleChange() {
    const role = document.getElementById("new-user-role").value;
    const ragContainer = document.getElementById("create-user-rag-container");
    if (!ragContainer) return;

    if (role === "admin") {
        ragContainer.classList.add("opacity-50", "pointer-events-none");
    } else {
        ragContainer.classList.remove("opacity-50", "pointer-events-none");
    }
}

function onEditUserRoleChange() {
    const role = document.getElementById("edit-user-role").value;
    const ragContainer = document.getElementById("edit-user-rag-container");
    if (!ragContainer) return;

    if (role === "admin") {
        ragContainer.classList.add("opacity-50", "pointer-events-none");
    } else {
        ragContainer.classList.remove("opacity-50", "pointer-events-none");
    }
}

async function loadUsers() {
    const tbody = document.getElementById("users-table-body");
    const countBadge = document.getElementById("users-count-badge");
    if (!tbody) return;

    try {
        // Cargar en paralelo usuarios y bases RAG si aún no fueron cargadas
        const [usersResp] = await Promise.all([
            fetch("/api/users"),
            cachedRagBases.length === 0 ? fetchAvailableRagBases() : Promise.resolve()
        ]);

        if (!usersResp.ok) {
            if (usersResp.status === 403) return; // No es admin
            throw new Error(`HTTP ${usersResp.status}`);
        }

        const users = await usersResp.json();
        cachedUsersMap.clear();
        users.forEach(u => cachedUsersMap.set(u.username.toLowerCase(), u));

        if (countBadge) {
            countBadge.textContent = `${users.length + 1} usuarios`; // +1 por el admin local
        }

        // Mantener únicamente la primera fila (admin local)
        const adminRow = tbody.querySelector("tr:first-child");
        tbody.innerHTML = "";
        if (adminRow) {
            tbody.appendChild(adminRow);
        }

        users.forEach(u => {
            const tr = document.createElement("tr");
            tr.className = "hover:bg-slate-800/30 transition-colors";

            const roleBadge = u.role === "admin"
                ? `<span class="px-2 py-0.5 rounded-md bg-purple-500/15 text-purple-300 border border-purple-500/30 text-[11px] font-sans font-semibold">Administrador</span>`
                : `<span class="px-2 py-0.5 rounded-md bg-blue-500/15 text-blue-300 border border-blue-500/30 text-[11px] font-sans font-semibold">Operador</span>`;

            const statusBadge = u.is_active
                ? `<span class="inline-flex items-center gap-1.5 text-emerald-400 font-sans">
                     <svg class="h-2.5 w-2.5" fill="currentColor" viewBox="0 0 8 8"><circle cx="4" cy="4" r="3"/></svg>
                     Activo
                   </span>`
                : `<span class="inline-flex items-center gap-1.5 text-amber-400 font-sans">
                     <svg class="h-2.5 w-2.5" fill="currentColor" viewBox="0 0 8 8"><circle cx="4" cy="4" r="3"/></svg>
                     Suspendido
                   </span>`;

            // Renderizar insignias de bases RAG permitidas
            let ragBadges = "";
            const allowed = u.allowed_rag_tables || [];
            if (u.role === "admin" || allowed.includes("*")) {
                ragBadges = `<span class="px-2 py-0.5 rounded-md bg-purple-500/15 text-purple-300 border border-purple-500/30 text-[10px] font-sans">Todas (*)</span>`;
            } else if (allowed.length === 0) {
                ragBadges = `<span class="px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-300 border border-rose-500/30 text-[10px] font-sans">Ninguna</span>`;
            } else {
                ragBadges = allowed.map(tbl => {
                    const match = cachedRagBases.find(b => b.table_name === tbl);
                    const label = match ? (match.display_name || match.empresa || tbl) : tbl;
                    return `<span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-sans inline-block mr-1 mb-0.5" title="${escapeHtml(tbl)}">${escapeHtml(label)}</span>`;
                }).join("");
            }

            const lastLoginText = u.last_login 
                ? new Date(u.last_login).toLocaleString()
                : "Nunca";

            tr.innerHTML = `
                <td class="px-6 py-4 font-sans font-medium text-slate-100 flex items-center gap-2">
                    <span class="h-2 w-2 rounded-full ${u.is_active ? 'bg-sky-400' : 'bg-slate-500'}"></span>
                    <span class="font-semibold">${escapeHtml(u.username)}</span>
                </td>
                <td class="px-6 py-4">${roleBadge}</td>
                <td class="px-6 py-4">${statusBadge}</td>
                <td class="px-6 py-4 max-w-xs">${ragBadges}</td>
                <td class="px-6 py-4 text-slate-400 font-sans">${escapeHtml(u.created_by || 'admin')}</td>
                <td class="px-6 py-4 text-slate-400 font-sans">${lastLoginText}</td>
                <td class="px-6 py-4 text-right font-sans space-x-1.5 whitespace-nowrap">
                    <button onclick="openEditUserModal('${escapeHtml(u.username)}')" 
                        title="Editar rol, estado y bases RAG"
                        class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-[11px] transition-all">
                        Editar
                    </button>
                    <button onclick="toggleUserStatus('${escapeHtml(u.username)}', ${u.is_active})" 
                        title="${u.is_active ? 'Suspender cuenta' : 'Reactivar cuenta'}"
                        class="px-2.5 py-1 rounded-lg ${u.is_active ? 'bg-amber-500/10 text-amber-300 hover:bg-amber-500/20 border border-amber-500/30' : 'bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 border border-emerald-500/30'} text-[11px] transition-all">
                        ${u.is_active ? 'Suspender' : 'Activar'}
                    </button>
                    <button onclick="openResetPasswordModal('${escapeHtml(u.username)}')"
                        title="Cambiar contraseña"
                        class="px-2.5 py-1 rounded-lg bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20 border border-indigo-500/30 text-[11px] transition-all">
                        Clave
                    </button>
                    <button onclick="deleteUser('${escapeHtml(u.username)}')"
                        title="Eliminar usuario"
                        class="px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-300 hover:bg-rose-500/20 border border-rose-500/30 text-[11px] transition-all">
                        Eliminar
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error al cargar lista de usuarios:", err);
    }
}

async function openCreateUserModal() {
    const modal = document.getElementById("modal-create-user");
    const errBox = document.getElementById("create-user-error");
    if (errBox) errBox.classList.add("hidden");
    document.getElementById("form-create-user").reset();

    if (cachedRagBases.length === 0) {
        await fetchAvailableRagBases();
    }
    renderRagCheckboxes("create-user-rag-list", ["teccam_knowledge_base"]);
    onNewUserRoleChange();

    if (modal) modal.classList.remove("hidden");
}

function closeCreateUserModal() {
    const modal = document.getElementById("modal-create-user");
    if (modal) modal.classList.add("hidden");
}

async function handleCreateUserSubmit(event) {
    event.preventDefault();
    const username = document.getElementById("new-user-username").value.trim();
    const password = document.getElementById("new-user-password").value;
    const role = document.getElementById("new-user-role").value;
    const errBox = document.getElementById("create-user-error");

    let allowed_rag_tables = [];
    if (role === "admin") {
        allowed_rag_tables = ["*"];
    } else {
        const checkedBoxes = document.querySelectorAll("#create-user-rag-list input[type='checkbox']:checked");
        allowed_rag_tables = Array.from(checkedBoxes).map(cb => cb.value);
        if (allowed_rag_tables.length === 0) {
            if (errBox) {
                errBox.textContent = "Debe seleccionar al menos una base RAG permitida para el operador.";
                errBox.classList.remove("hidden");
            }
            return;
        }
    }

    try {
        const resp = await fetch("/api/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password, role, allowed_rag_tables })
        });
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || "Error al crear usuario.");
        }

        closeCreateUserModal();
        await loadUsers();
    } catch (err) {
        if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove("hidden");
        }
    }
}

async function openEditUserModal(username) {
    const user = cachedUsersMap.get(username.toLowerCase());
    if (!user) {
        alert("Usuario no encontrado en caché local.");
        return;
    }

    const modal = document.getElementById("modal-edit-user");
    const errBox = document.getElementById("edit-user-error");
    if (errBox) errBox.classList.add("hidden");

    document.getElementById("edit-user-username").value = user.username;
    document.getElementById("edit-user-username-display").textContent = user.username;
    document.getElementById("edit-user-role").value = user.role;
    document.getElementById("edit-user-active").checked = Boolean(user.is_active);

    if (cachedRagBases.length === 0) {
        await fetchAvailableRagBases();
    }

    renderRagCheckboxes("edit-user-rag-list", user.allowed_rag_tables || ["teccam_knowledge_base"]);
    onEditUserRoleChange();

    if (modal) modal.classList.remove("hidden");
}

function closeEditUserModal() {
    const modal = document.getElementById("modal-edit-user");
    if (modal) modal.classList.add("hidden");
}

async function handleEditUserSubmit(event) {
    event.preventDefault();
    const username = document.getElementById("edit-user-username").value;
    const role = document.getElementById("edit-user-role").value;
    const is_active = document.getElementById("edit-user-active").checked;
    const errBox = document.getElementById("edit-user-error");

    let allowed_rag_tables = [];
    if (role === "admin") {
        allowed_rag_tables = ["*"];
    } else {
        const checkedBoxes = document.querySelectorAll("#edit-user-rag-list input[type='checkbox']:checked");
        allowed_rag_tables = Array.from(checkedBoxes).map(cb => cb.value);
        if (allowed_rag_tables.length === 0) {
            if (errBox) {
                errBox.textContent = "Debe seleccionar al menos una base RAG permitida para el operador.";
                errBox.classList.remove("hidden");
            }
            return;
        }
    }

    try {
        const resp = await fetch(`/api/users/${encodeURIComponent(username)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role, is_active, allowed_rag_tables })
        });
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || "Error al actualizar usuario.");
        }

        closeEditUserModal();
        await loadUsers();
    } catch (err) {
        if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove("hidden");
        }
    }
}

function openResetPasswordModal(username) {
    const modal = document.getElementById("modal-reset-password");
    const errBox = document.getElementById("reset-password-error");
    if (errBox) errBox.classList.add("hidden");
    document.getElementById("form-reset-password").reset();
    document.getElementById("reset-password-username").value = username;
    document.getElementById("reset-password-target-user").textContent = username;
    if (modal) modal.classList.remove("hidden");
}

function closeResetPasswordModal() {
    const modal = document.getElementById("modal-reset-password");
    if (modal) modal.classList.add("hidden");
}

async function handleResetPasswordSubmit(event) {
    event.preventDefault();
    const username = document.getElementById("reset-password-username").value;
    const password = document.getElementById("reset-password-input").value;
    const errBox = document.getElementById("reset-password-error");

    try {
        const resp = await fetch(`/api/users/${encodeURIComponent(username)}/password`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password })
        });
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || "Error al restablecer la contraseña.");
        }

        closeResetPasswordModal();
        alert(`Contraseña actualizada con éxito para el usuario '${username}'.`);
    } catch (err) {
        if (errBox) {
            errBox.textContent = err.message;
            errBox.classList.remove("hidden");
        }
    }
}

async function toggleUserStatus(username, currentStatus) {
    const action = currentStatus ? "suspender" : "activar";
    if (!confirm(`¿Desea ${action} la cuenta del usuario '${username}'?`)) {
        return;
    }

    try {
        const resp = await fetch(`/api/users/${encodeURIComponent(username)}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ is_active: !currentStatus })
        });
        const data = await resp.json();
        if (!resp.ok) {
            throw new Error(data.error || "Error al actualizar estado.");
        }
        await loadUsers();
    } catch (err) {
        alert(err.message);
    }
}

async function deleteUser(username) {
    if (!confirm(`¿Está seguro de eliminar definitivamente al usuario '${username}'? Esta acción es irreversible.`)) {
        return;
    }

    try {
        const resp = await fetch(`/api/users/${encodeURIComponent(username)}`, {
            method: "DELETE"
        });
        const data = await resp.json();
        if (!resp.ok) {
            throw new Error(data.error || "Error al eliminar usuario.");
        }
        await loadUsers();
    } catch (err) {
        alert(err.message);
    }
}

function escapeHtml(text) {
    if (!text) return "";
    return text.toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
