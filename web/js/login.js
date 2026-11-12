import { db } from "./cliente.js?v=1";

const $ = (id) => document.getElementById(id);
let registrando = false;

const { data: { session } } = await db.auth.getSession();
if (session) location.replace("app.html");

function aviso(texto, tipo = "") {
  $("mensaje").textContent = texto;
  $("mensaje").className = `mensaje ${tipo}`;
}

$("cambiar").addEventListener("click", () => {
  registrando = !registrando;
  $("titulo").textContent = registrando ? "Crea tu cuenta" : "Inicia sesión";
  $("enviar").textContent = registrando ? "Crear cuenta" : "Iniciar sesión";
  $("cambiar").textContent = registrando ? "Ya tengo una cuenta" : "Crear una cuenta";
  $("clave").autocomplete = registrando ? "new-password" : "current-password";
  aviso("");
});

function traducir(error) {
  const m = error.message.toLowerCase();
  if (m.includes("invalid login")) return "El correo o la contraseña no coinciden. Revísalos e intenta de nuevo.";
  if (m.includes("already registered")) return "Ese correo ya tiene una cuenta. Inicia sesión.";
  if (m.includes("password")) return "La contraseña debe tener al menos 8 caracteres.";
  if (m.includes("rate limit")) return "Hubo demasiados intentos. Espera unos minutos e intenta de nuevo.";
  return `No se pudo completar la solicitud: ${error.message}`;
}

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("enviar").disabled = true;
  aviso("");
  const credenciales = { email: $("correo").value.trim(), password: $("clave").value };
  const { data, error } = registrando
    ? await db.auth.signUp(credenciales)
    : await db.auth.signInWithPassword(credenciales);
  $("enviar").disabled = false;
  if (error) return aviso(traducir(error), "error");
  if (data.session) return location.replace("app.html");
  aviso("Cuenta creada. Revisa tu correo para confirmarla y luego inicia sesión.", "ok");
});
