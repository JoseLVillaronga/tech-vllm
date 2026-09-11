/**
 * dashboard_users.js - Controlador Frontend para la Gestión de Usuarios Remotos.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Si la pestaña de usuarios está visible o se activa, cargar usuarios
    const btnUsers = document.getElementById("btn-users");
    if (btnUsers) {
        btnUsers.addEventListener("click", () => {
            loadUsers();
        });
    }
});

async function loadUsers() {
    const tbody = document.getElementById("users-table-body");
    const countBadge = document.getElementById("users-count-badge");
    if (!tbody) return;

    try {
        const response = await fetch("/api/users");
        if (!response.ok) {
            if (response.status === 403) {
                // No es administrador, no tiene permiso
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }

        const users = await response.json();
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
                <td class="px-6 py-4 text-slate-400 font-sans">${escapeHtml(u.created_by || 'admin')}</td>
                <td class="px-6 py-4 text-slate-400 font-sans">${lastLoginText}</td>
                <td class="px-6 py-4 text-right font-sans space-x-2">
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

function openCreateUserModal() {
    const modal = document.getElementById("modal-create-user");
    const errBox = document.getElementById("create-user-error");
    if (errBox) errBox.classList.add("hidden");
    document.getElementById("form-create-user").reset();
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

    try {
        const resp = await fetch("/api/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password, role })
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
