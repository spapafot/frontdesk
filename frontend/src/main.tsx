import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthGate } from "./components/AuthGate";
import { installAuthFetch } from "./lib/authFetch";
import "./index.css";

// Attach the Supabase JWT to admin API calls (no-op when auth is disabled).
installAuthFetch();

// The public marketing site now lives at the apex domain (the `site/` Astro
// project). This app subdomain is the workspace only: it goes straight to the
// auth gate, which shows the sign-in form until an admin is authenticated.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthGate>
        <App />
      </AuthGate>
    </BrowserRouter>
  </React.StrictMode>
);
