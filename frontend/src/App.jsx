const { useEffect, useMemo, useRef, useState, useCallback } = React;

const API_BASE = window.location.origin;

function createMessageId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [authMode, setAuthMode] = useState("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState("");

  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [messages, setMessages] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const messagesRef = useRef(null);
  const abortControllerRef = useRef(null);

  const chatHistory = useMemo(
    () => messages.filter((msg) => msg.role === "user" || msg.role === "assistant"),
    [messages]
  );

  // Carregar sessoes
  const loadSessions = useCallback(async () => {
    try {
      const data = await fetchSessions();
      setSessions(data);
      if (data.length > 0 && !activeSessionId) {
        setActiveSessionId(data[0].id);
      }
    } catch {
      // Ignora
    }
  }, [activeSessionId]);

  // Carregar mensagens de uma sessao
  const loadMessages = useCallback(async (sessionId) => {
    try {
      const res = await authFetch(`${API_BASE}/api/chat/history/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.length > 0 ? data : [
          { id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" },
        ]);
      }
    } catch {
      setMessages([
        { id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" },
      ]);
    }
  }, []);

  // Verificar login
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setLoading(false);
      return;
    }
    fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Token invalido");
        return res.json();
      })
      .then((data) => {
        setUser(data);
        setLoading(false);
        return loadSessions();
      })
      .catch(() => {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        setLoading(false);
      });
  }, [loadSessions]);

  // Carregar mensagens quando muda de sessao
  useEffect(() => {
    if (user && activeSessionId) {
      loadMessages(activeSessionId);
    }
  }, [activeSessionId, user, loadMessages]);

  useEffect(() => {
    const el = messagesRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const handleAuth = async (e) => {
    e.preventDefault();
    setAuthError("");
    try {
      const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/register";
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: authEmail, password: authPassword }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Erro de autenticacao.");
      }
      if (authMode === "login") {
        const data = await res.json();
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        const meRes = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        const meData = await meRes.json();
        setUser(meData);
        const sess = await fetchSessions();
        setSessions(sess);
        if (sess.length > 0) setActiveSessionId(sess[0].id);
      } else {
        setAuthMode("login");
        setAuthError("Conta criada! Faca login.");
      }
    } catch (err) {
      setAuthError(err.message);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
      });
    } catch {}
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setUser(null);
    setSessions([]);
    setActiveSessionId(null);
    setMessages([]);
  };

  const handleNewSession = async () => {
    try {
      const session = await createSession();
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      setMessages([
        { id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" },
      ]);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDeleteSession = async (sessionId, e) => {
    e.stopPropagation();
    try {
      await deleteSession(sessionId);
      const updated = sessions.filter((s) => s.id !== sessionId);
      setSessions(updated);
      if (activeSessionId === sessionId) {
        if (updated.length > 0) {
          setActiveSessionId(updated[0].id);
        } else {
          const session = await createSession();
          setSessions([session]);
          setActiveSessionId(session.id);
          setMessages([
            { id: createMessageId(), role: "assistant", content: "Bem-vindo ao ChatLLM Lab. Como posso ajudar voce hoje?" },
          ]);
        }
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const onStop = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setBusy(false);
  };

  const onSubmit = async (event, inputRef) => {
    event.preventDefault();
    const cleaned = text.trim();
    if (!cleaned || busy) return;

    // Garantir que existe uma sessao ativa
    let sessionId = activeSessionId;
    if (!sessionId) {
      try {
        const session = await createSession();
        setSessions((prev) => [session, ...prev]);
        setActiveSessionId(session.id);
        sessionId = session.id;
      } catch (err) {
        setError(err.message);
        return;
      }
    }

    setError("");
    const userMessage = { id: createMessageId(), role: "user", content: cleaned };
    const assistantMessageId = createMessageId();

    setMessages((prev) => [
      ...prev,
      userMessage,
      { id: assistantMessageId, role: "assistant", content: "" },
    ]);
    setText("");
    setBusy(true);
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      await sendMessageStream({
        message: cleaned,
        history: chatHistory,
        sessionId,
        signal: abortController.signal,
        onDelta: (delta) => {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessageId ? { ...msg, content: `${msg.content}${delta}` } : msg
            )
          );
        },
      });

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId && !msg.content.trim()
            ? { ...msg, content: "Nao foi possivel obter resposta do modelo agora." }
            : msg
        )
      );

      // Recarrega sessoes para pegar titulo atualizado
      const sess = await fetchSessions();
      setSessions(sess);
    } catch (err) {
      const aborted = err?.name === "AbortError";
      if (!aborted) {
        setError(err.message || "Falha inesperada ao gerar resposta.");
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? { ...msg, content: msg.content.trim() ? msg.content : "Nao foi possivel obter resposta do modelo agora." }
              : msg
          )
        );
      } else {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId && !msg.content.trim()
              ? { ...msg, content: "Resposta interrompida." }
              : msg
          )
        );
      }
    } finally {
      abortControllerRef.current = null;
      setBusy(false);
    }
  };

  // Tela de carregamento
  if (loading) {
    return (
      <main className="app-shell">
        <div className="auth-container">
          <div className="auth-card">
            <p>Verificando autenticacao...</p>
          </div>
        </div>
      </main>
    );
  }

  // Tela de autenticacao
  if (!user) {
    return (
      <main className="app-shell">
        <div className="auth-container">
          <div className="auth-card">
            <h1 className="auth-title">ChatLLM Lab</h1>
            <h2 className="auth-subtitle">
              {authMode === "login" ? "Entrar" : "Criar conta"}
            </h2>
            {authError && <div className="auth-error">{authError}</div>}
            <form onSubmit={handleAuth} className="auth-form">
              <input type="email" placeholder="Email" value={authEmail} onChange={(e) => setAuthEmail(e.target.value)} required autoFocus />
              <input type="password" placeholder="Senha" value={authPassword} onChange={(e) => setAuthPassword(e.target.value)} required minLength={6} />
              <button type="submit">{authMode === "login" ? "Entrar" : "Criar conta"}</button>
            </form>
            <p className="auth-toggle">
              {authMode === "login" ? (
                <>Nao tem conta? <a href="#" onClick={(e) => { e.preventDefault(); setAuthMode("register"); setAuthError(""); }}>Cadastre-se</a></>
              ) : (
                <>Ja tem conta? <a href="#" onClick={(e) => { e.preventDefault(); setAuthMode("login"); setAuthError(""); }}>Faca login</a></>
              )}
            </p>
          </div>
        </div>
      </main>
    );
  }

  // Chat logado com sidebar
  return (
    <main className="app-shell">
      <div className={`app-layout ${sidebarOpen ? "sidebar-open" : ""}`}>
        {sidebarOpen && (
          <aside className="sidebar">
            <div className="sidebar-header">
              <button className="new-chat-btn" onClick={handleNewSession} title="Nova conversa">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="8" y1="1" x2="8" y2="15" />
                  <line x1="1" y1="8" x2="15" y2="8" />
                </svg>
                Nova conversa
              </button>
            </div>
            <div className="sidebar-list">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`sidebar-item ${s.id === activeSessionId ? "active" : ""}`}
                  onClick={() => setActiveSessionId(s.id)}
                >
                  <span className="sidebar-item-title">{s.title}</span>
                  <button className="sidebar-item-del" onClick={(e) => handleDeleteSession(s.id, e)} title="Deletar">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <line x1="2" y1="2" x2="12" y2="12" />
                      <line x1="12" y1="2" x2="2" y2="12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          </aside>
        )}

        <div className="app-main">
          <header className="app-header">
            <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)} title="Alternar sidebar">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="4" x2="17" y2="4" />
                <line x1="3" y1="10" x2="17" y2="10" />
                <line x1="3" y1="16" x2="17" y2="16" />
              </svg>
            </button>
            <div className="brand">ChatLLM Lab</div>
            <div className="header-right">
              <span className="user-email">{user.email}</span>
              <button className="logout-btn" onClick={handleLogout}>Sair</button>
            </div>
          </header>

          <section className="messages" aria-live="polite" ref={messagesRef}>
            <div className="messages-inner">
              {messages.map((msg) => (
                <article key={msg.id} className={`bubble ${msg.role}`}>
                  <MessageContent content={msg.content} />
                </article>
              ))}
            </div>
          </section>

          <Composer
            text={text}
            busy={busy}
            error={error}
            onChangeText={setText}
            onSubmit={onSubmit}
            onStop={onStop}
          />

          <div className="warning-banner">Lembre-se, voce precisa focar no experimento!!!</div>
        </div>
      </div>
    </main>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);

