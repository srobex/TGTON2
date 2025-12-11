import React from "react";
import { createRoot } from "react-dom/client";

const App = () => {
  return (
    <main style={{ fontFamily: "sans-serif", padding: 24 }}>
      <h1>HyperSniper Mini App</h1>
      <p>Подключи Ton Connect, введи JWT от бота и начни торговать.</p>
    </main>
  );
};

const root = createRoot(document.getElementById("root")!);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);




