import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { Home } from "./pages/Home";
import { Login } from "./pages/Login";
import { Voice } from "./pages/Voice";
import { Settings } from "./pages/Settings";
import { getOperator } from "./lib/auth";

import "./theme.css";
import "./shell.css";


export default function App() {
  const [hasOperator, setHasOperator] = useState<boolean | null>(null);

  useEffect(() => {
    getOperator().then((op) => setHasOperator(op !== null));
  }, []);

  if (hasOperator === null) {
    return <div className="page page-loading"><div className="muted">Loading…</div></div>;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Layout />}>
          <Route path="/" element={hasOperator ? <Home /> : <Navigate to="/login" replace />} />
          <Route path="/voice" element={hasOperator ? <Voice /> : <Navigate to="/login" replace />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
