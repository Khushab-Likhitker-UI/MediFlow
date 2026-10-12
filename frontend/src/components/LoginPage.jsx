import React, { useState } from 'react';
import { Lock, Mail, ShieldCheck, ArrowRight, AlertCircle, Activity, Database, FlaskConical } from 'lucide-react';
import { api, getApiMode, setApiMode } from '../api/adapter';
import { API_BASE_URL } from '../config';

export const LoginPage = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState(getApiMode);

  const handleToggleMode = (newMode) => {
    try {
      setApiMode(newMode);
      setMode(newMode);
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const userData = await api.login(email.trim(), password);
      onLogin(userData);
    } catch (err) {
      setError(err.message || `Unable to authenticate. Ensure the backend API (${API_BASE_URL}) is reachable.`);
    } finally {
      setLoading(false);
    }
  };

  const fillDemoCredentials = () => {
    setEmail('admin@smarthealth.local');
    setPassword('admin123');
    setError('');
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white flex flex-col items-center justify-center p-6 relative overflow-hidden font-sans">
      {/* Background Subtle Glows */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-red-600/10 rounded-full blur-3xl pointer-events-none animate-pulse"></div>
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none"></div>

      {/* Main Login Card */}
      <div className="w-full max-w-md bg-[#111111] border-2 border-neutral-800 p-8 sm:p-10 relative z-10 shadow-[0_20px_50px_rgba(0,0,0,0.8)] flex flex-col items-center">
        
        {/* KRAFT Diamond Logo */}
        <div className="w-16 h-16 border-2 border-white flex items-center justify-center mb-8 transform rotate-45 shadow-[0_0_20px_rgba(255,255,255,0.15)]">
          <div className="transform -rotate-45 font-black tracking-[0.2em] text-sm text-white">
            KRAFT
          </div>
        </div>

        <h1 className="text-sm font-bold tracking-[0.25em] text-white uppercase text-center">
          District Health Command
        </h1>
        <div className="text-[10px] text-neutral-400 mt-1 uppercase tracking-[0.2em] font-mono text-center mb-6 flex items-center justify-center gap-1.5">
          {mode === 'real' ? (
            <span className="flex items-center gap-1.5 text-emerald-400">
              <Database className="w-3 h-3" /> Live Backend ({API_BASE_URL})
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-amber-400">
              <FlaskConical className="w-3 h-3" /> Dev Adapter (Simulated Phase 1)
            </span>
          )}
        </div>

        {/* Development Mode Toggle */}
        {!api.isProduction && (
          <div className="mb-6 w-full flex items-center bg-neutral-900 border border-neutral-800 rounded p-1 text-[10px] font-mono">
            <button
              type="button"
              onClick={() => handleToggleMode('mock')}
              className={`flex-1 py-1 px-2 font-bold uppercase rounded transition-colors cursor-pointer text-center ${
                mode === 'mock'
                  ? 'bg-amber-500 text-black shadow-xs'
                  : 'text-neutral-400 hover:text-white'
              }`}
            >
              Dev Adapter (Mock)
            </button>
            <button
              type="button"
              onClick={() => handleToggleMode('real')}
              className={`flex-1 py-1 px-2 font-bold uppercase rounded transition-colors cursor-pointer text-center ${
                mode === 'real'
                  ? 'bg-emerald-500 text-black shadow-xs'
                  : 'text-neutral-400 hover:text-white'
              }`}
            >
              Live Backend
            </button>
          </div>
        )}

        {/* Demo Credentials Helper Pill */}
        <button
          type="button"
          onClick={fillDemoCredentials}
          className="mb-6 w-full py-2.5 px-4 bg-neutral-900/80 hover:bg-neutral-800 border border-neutral-700/80 rounded transition-all text-left flex items-center justify-between group cursor-pointer"
        >
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <div>
              <div className="text-[10px] uppercase tracking-wider text-neutral-400 font-bold">
                Click to auto-fill demo login (Supabase):
              </div>
              <div className="text-xs font-mono text-emerald-400 mt-0.5">
                admin@smarthealth.local / admin123
              </div>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-neutral-500 group-hover:text-white group-hover:translate-x-1 transition-all" />
        </button>

        {/* Error Banner */}
        {error && (
          <div className="w-full mb-6 p-3 bg-red-950/60 border border-red-500/50 text-red-300 text-xs flex items-center gap-2.5 animate-fade-in">
            <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleLogin} className="w-full space-y-5">
          <div>
            <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-2">
              Officer Email / Username
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-neutral-500">
                <Mail className="w-4 h-4" />
              </div>
              <input
                type="text"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@smarthealth.local"
                className="w-full bg-[#0a0a0a] border border-neutral-700 focus:border-white px-3.5 py-3 pl-10 text-xs text-white placeholder-neutral-600 focus:outline-none transition-colors font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-2">
              Security Clearance Password
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-neutral-500">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-[#0a0a0a] border border-neutral-700 focus:border-white px-3.5 py-3 pl-10 text-xs text-white placeholder-neutral-600 focus:outline-none transition-colors font-mono"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-3.5 bg-white text-[#111111] hover:bg-neutral-200 font-bold text-xs uppercase tracking-[0.2em] transition-all flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(255,255,255,0.2)] disabled:opacity-50 cursor-pointer"
          >
            {loading ? (
              <>
                <Activity className="w-4 h-4 animate-spin" />
                <span>Authenticating with Supabase...</span>
              </>
            ) : (
              <>
                <span>Authorize Access</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Footer info */}
        <div className="mt-8 pt-6 border-t border-neutral-800/80 w-full flex justify-between items-center text-[10px] text-neutral-500 font-mono">
          <span>SYS_VER: 4.2.0-SUPABASE</span>
          <span>SEC: ENCRYPTED_SSL</span>
        </div>
      </div>
    </div>
  );
};
