
import os

BASE = r"E:\Freelancing\financehub"

def w(rel, txt):
    path = os.path.join(BASE, rel.replace('/', os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(txt.lstrip('\n'))
    print("  OK " + rel)

print("\n  Writing HTML templates...\n")

BASE_HTML = """
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>{% block title %}FinanceHub{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"><\/script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"><\/script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *{font-family:'Inter',sans-serif;}
    .sidebar-link{display:flex;align-items:center;gap:10px;padding:9px 14px;border-radius:8px;font-size:.85rem;font-weight:500;color:#94a3b8;transition:all .15s;text-decoration:none;}
    .sidebar-link:hover{background:rgba(255,255,255,.07);color:#e2e8f0;}
    .sidebar-link.active{background:#1e3a5f;color:#fff;}
    .form-input{width:100%;padding:.55rem .8rem;border:1px solid #d1d9e6;border-radius:8px;font-size:.875rem;background:#f8fafc;color:#1e293b;outline:none;transition:border .15s,box-shadow .15s;}
    .form-input:focus{border-color:#2a4a7f;box-shadow:0 0 0 3px rgba(42,74,127,.1);background:#fff;}
    .form-input::placeholder{color:#94a3b8;}
    .btn{display:inline-flex;align-items:center;gap:6px;padding:.5rem 1rem;border-radius:8px;font-size:.85rem;font-weight:600;cursor:pointer;border:none;transition:all .15s;text-decoration:none;}
    .btn-navy{background:#0f2044;color:#fff;}.btn-navy:hover{background:#1a3260;}
    .btn-outline{background:#fff;color:#374151;border:1px solid #d1d9e6;}.btn-outline:hover{background:#f1f5f9;}
    .btn-danger{background:#fee2e2;color:#dc2626;border:1px solid #fecaca;}
    .btn-success{background:#dcfce7;color:#16a34a;border:1px solid #bbf7d0;}
    .card{background:#fff;border-radius:12px;padding:1.25rem;box-shadow:0 1px 3px rgba(0,0,0,.06);}
    .badge{display:inline-flex;align-items:center;padding:2px 9px;border-radius:999px;font-size:.72rem;font-weight:600;}
    .badge-green{background:#dcfce7;color:#15803d;}
    .badge-red{background:#fee2e2;color:#b91c1c;}
    .badge-yellow{background:#fef9c3;color:#a16207;}
    .badge-blue{background:#dbeafe;color:#1d4ed8;}
    .badge-slate{background:#f1f5f9;color:#475569;}
    .table-row:hover{background:#f8fafc;}
    ::-webkit-scrollbar{width:5px;height:5px;}
    ::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:9999px;}
  </style>
  {% block head %}{% endblock %}
</head>
<body class="h-full bg-slate-50">
<div id="sidebar-overlay" class="hidden fixed inset-0 bg-black/40 z-30 lg:hidden"></div>
<div class="flex h-full">
  <aside id="mobile-sidebar" class="fixed top-0 left-0 h-full w-60 z-40 -translate-x-full lg:translate-x-0 lg:static lg:flex lg:flex-col transition-transform duration-200" style="background:#0f2044">
    <div class="flex items-center gap-2.5 px-5 py-5 border-b border-white/10">
      <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style="background:#c9a84c">
        <svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M2 8h12M8 2v12" stroke="#0f2044" stroke-width="2.5" stroke-linecap="round"/><\/svg>
      </div>
      <div>
        <div class="text-white font-semibold text-sm">Finance<span style="color:#c9a84c">Hub<\/span><\/div>
        <div class="text-blue-300 text-xs opacity-60">{{ request.user.role|capfirst }}<\/div>
      </div>
    </div>
    <nav class="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
      <p class="text-blue-400 text-xs font-semibold uppercase tracking-widest px-3 mb-2 opacity-50">Main<\/p>
      <a href="{% url 'dashboard:index' %}" class="sidebar-link {% block nav_dashboard %}{% endblock %}">
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><\/svg>Dashboard
      <\/a>
      <a href="{% url 'finance:list' %}" class="sidebar-link {% block nav_finance %}{% endblock %}">
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/><\/svg>Finance
      <\/a>
      <a href="{% url 'projects:list' %}" class="sidebar-link {% block nav_projects %}{% endblock %}">
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/><\/svg>Projects
      <\/a>
      <a href="{% url 'clients:list' %}" class="sidebar-link {% block nav_clients %}{% endblock %}">
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/><\/svg>Clients
      <\/a>
      <a href="{% url 'invoices:list' %}" class="sidebar-link {% block nav_invoices %}{% endblock %}">
        <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/><\/svg>Invoices
      <\/a>
      <div class="pt-3">
        <p class="text-blue-400 text-xs font-semibold uppercase tracking-widest px-3 mb-2 opacity-50">Analytics<\/p>
        <a href="{% url 'reports:index' %}" class="sidebar-link {% block nav_reports %}{% endblock %}">
          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/><\/svg>Reports
        <\/a>
      <\/div>
    <\/nav>
    <div class="px-3 py-4 border-t border-white/10">
      <div class="flex items-center gap-3 px-2 mb-3">
        <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0" style="background:#1e3a5f">{{ request.user.initials }}<\/div>
        <div class="min-w-0">
          <div class="text-white text-xs font-medium truncate">{{ request.user.full_name|default:request.user.username }}<\/div>
          <div class="text-blue-300 text-xs opacity-60 truncate">{{ request.user.email }}<\/div>
        <\/div>
      <\/div>
      <a href="{% url 'accounts:logout' %}" class="sidebar-link w-full">
        <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/><\/svg>Sign out
      <\/a>
    <\/div>
  <\/aside>
  <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
    <header class="bg-white border-b border-slate-100 px-5 py-3.5 flex items-center gap-4 flex-shrink-0">
      <button id="menu-btn" class="lg:hidden text-slate-500">
        <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M4 6h16M4 12h16M4 18h16"/><\/svg>
      <\/button>
      <div class="flex-1">
        <h1 class="text-slate-800 font-semibold text-base leading-tight">{% block page_title %}Dashboard{% endblock %}<\/h1>
        <p class="text-slate-400 text-xs">{% block page_sub %}{% endblock %}<\/p>
      <\/div>
      <div class="flex items-center gap-2">{% block header_actions %}{% endblock %}<\/div>
    <\/header>
    <div class="px-5 pt-3 space-y-2 flex-shrink-0">
      {% for msg in messages %}
        <div class="alert-msg flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium {% if msg.tags == 'success' %}bg-green-50 text-green-700 border border-green-200{% elif msg.tags == 'error' %}bg-red-50 text-red-600 border border-red-200{% else %}bg-blue-50 text-blue-700 border border-blue-200{% endif %}">{{ msg }}<\/div>
      {% endfor %}
    <\/div>
    <main class="flex-1 overflow-y-auto p-5 pb-20 lg:pb-6">{% block content %}{% endblock %}<\/main>
  <\/div>
<\/div>
<nav class="lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 flex z-20">
  <a href="{% url 'dashboard:index' %}" class="flex-1 flex flex-col items-center py-2 text-slate-400" style="font-size:.6rem;gap:3px">
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><\/svg>Home<\/a>
  <a href="{% url 'finance:list' %}" class="flex-1 flex flex-col items-center py-2 text-slate-400" style="font-size:.6rem;gap:3px">
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path stroke-linecap="round" d="M12 8v8m-3-4h6"/><\/svg>Finance<\/a>
  <a href="{% url 'projects:list' %}" class="flex-1 flex flex-col items-center py-2 text-slate-400" style="font-size:.6rem;gap:3px">
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/><\/svg>Projects<\/a>
  <a href="{% url 'invoices:list' %}" class="flex-1 flex flex-col items-center py-2 text-slate-400" style="font-size:.6rem;gap:3px">
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/><\/svg>Invoices<\/a>
  <a href="{% url 'reports:index' %}" class="flex-1 flex flex-col items-center py-2 text-slate-400" style="font-size:.6rem;gap:3px">
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/><\/svg>Reports<\/a>
<\/nav>
<script src="/static/js/main.js"><\/script>
{% block scripts %}{% endblock %}
<\/body><\/html>
"""

w("templates/base.html", BASE_HTML)

LOGIN_HTML = """
<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Sign In - FinanceHub<\/title>
<script src="https://cdn.tailwindcss.com"><\/script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>body{font-family:'Inter',sans-serif;}.fi{width:100%;padding:.6rem .85rem;border:1px solid #d1d9e6;border-radius:8px;font-size:.875rem;background:#f8fafc;outline:none;transition:border .15s,box-shadow .15s;}.fi:focus{border-color:#2a4a7f;box-shadow:0 0 0 3px rgba(42,74,127,.1);background:#fff;}.fi::placeholder{color:#94a3b8;}.fi.err{border-color:#dc2626;}.gb{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);background-size:48px 48px;}<\/style><\/head>
<body class="min-h-screen bg-slate-50 flex">
  <div class="hidden lg:flex lg:w-5/12 relative overflow-hidden flex-col justify-between p-12" style="background:#0f2044">
    <div class="gb"><\/div>
    <div class="relative z-10 flex items-center gap-2.5">
      <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background:#c9a84c"><svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M2 8h12M8 2v12" stroke="#0f2044" stroke-width="2.5" stroke-linecap="round"/><\/svg><\/div>
      <span class="text-white font-semibold">Finance<span style="color:#c9a84c">Hub<\/span><\/span>
    <\/div>
    <div class="relative z-10">
      <h2 class="text-white text-3xl font-light leading-snug mb-4">Manage your<br><span class="font-semibold">business finances<\/span><br>in one place.<\/h2>
      <p class="text-blue-200 text-sm opacity-75 max-w-xs leading-relaxed">Track expenses, invoices, clients and projects — all in one professional platform.<\/p>
      <div class="mt-8 grid grid-cols-3 gap-4">
        <div><div class="font-semibold" style="color:#c9a84c">Real-time<\/div><div class="text-blue-300 text-xs opacity-60 mt-0.5">Reports<\/div><\/div>
        <div><div class="font-semibold" style="color:#c9a84c">Multi-role<\/div><div class="text-blue-300 text-xs opacity-60 mt-0.5">Access<\/div><\/div>
        <div><div class="font-semibold" style="color:#c9a84c">Full<\/div><div class="text-blue-300 text-xs opacity-60 mt-0.5">Control<\/div><\/div>
      <\/div>
    <\/div>
    <p class="relative z-10 text-blue-300 text-xs opacity-40">© 2025 FinanceHub<\/p>
  <\/div>
  <div class="flex-1 flex items-center justify-center px-6 py-12 sm:px-12">
    <div class="w-full max-w-sm">
      <h1 class="text-2xl font-semibold text-slate-800 mb-1">Welcome back<\/h1>
      <p class="text-slate-400 text-sm mb-7">Sign in to your account<\/p>
      {% if form.non_field_errors %}<div class="mb-5 px-4 py-3 rounded-lg bg-red-50 border border-red-200">{% for e in form.non_field_errors %}<p class="text-red-600 text-sm">{{ e }}<\/p>{% endfor %}<\/div>{% endif %}
      {% for msg in messages %}<div class="mb-4 px-4 py-3 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-sm">{{ msg }}<\/div>{% endfor %}
      <form method="post" novalidate>
        {% csrf_token %}
        <div class="mb-4">
          <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">Email<\/label>
          <input type="email" name="email" value="{{ form.email.value|default:'' }}" class="fi {% if form.email.errors %}err{% endif %}" placeholder="you@company.com" autocomplete="email"/>
          {% if form.email.errors %}<p class="text-red-500 text-xs mt-1">{{ form.email.errors.0 }}<\/p>{% endif %}
        <\/div>
        <div class="mb-6">
          <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">Password<\/label>
          <div class="relative">
            <input type="password" name="password" id="pwd" class="fi {% if form.password.errors %}err{% endif %}" placeholder="••••••••" autocomplete="current-password"/>
            <button type="button" onclick="var f=document.getElementById('pwd');f.type=f.type==='password'?'text':'password'" class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/><\/svg>
            <\/button>
          <\/div>
          {% if form.password.errors %}<p class="text-red-500 text-xs mt-1">{{ form.password.errors.0 }}<\/p>{% endif %}
        <\/div>
        <button type="submit" class="w-full py-2.5 rounded-lg text-white font-semibold text-sm" style="background:#0f2044">Sign in to FinanceHub<\/button>
      <\/form>
      <p class="text-center text-slate-400 text-sm mt-5">No account? <a href="{% url 'accounts:register' %}" class="font-medium" style="color:#0f2044">Create one<\/a><\/p>
    <\/div>
  <\/div>
<\/body><\/html>
"""
w("templates/accounts/login.html", LOGIN_HTML)

REGISTER_HTML = """
<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Register - FinanceHub<\/title>
<script src="https://cdn.tailwindcss.com"><\/script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>body{font-family:'Inter',sans-serif;}.fi{width:100%;padding:.6rem .85rem;border:1px solid #d1d9e6;border-radius:8px;font-size:.875rem;background:#f8fafc;outline:none;transition:border .15s;}.fi:focus{border-color:#2a4a7f;box-shadow:0 0 0 3px rgba(42,74,127,.1);background:#fff;}.fi::placeholder{color:#94a3b8;}.fi.err{border-color:#dc2626;}.gb{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);background-size:48px 48px;}.sb div{height:3px;border-radius:999px;transition:background .3s;}<\/style><\/head>
<body class="min-h-screen bg-slate-50 flex">
  <div class="hidden lg:flex lg:w-5/12 relative overflow-hidden flex-col justify-between p-12" style="background:#0f2044">
    <div class="gb"><\/div>
    <div class="relative z-10 flex items-center gap-2.5">
      <div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background:#c9a84c"><svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M2 8h12M8 2v12" stroke="#0f2044" stroke-width="2.5" stroke-linecap="round"/><\/svg><\/div>
      <span class="text-white font-semibold">Finance<span style="color:#c9a84c">Hub<\/span><\/span>
    <\/div>
    <div class="relative z-10">
      <h2 class="text-white text-3xl font-light leading-snug mb-5">Start managing<br><span class="font-semibold">your finances<\/span><br>today.<\/h2>
      <div class="space-y-3">
        <div class="flex items-center gap-3"><div class="w-5 h-5 rounded-full flex items-center justify-center" style="background:rgba(201,168,76,.2)"><svg width="10" height="10" fill="none" viewBox="0 0 12 12"><path d="M2 6l3 3 5-5" stroke="#c9a84c" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><\/svg><\/div><span class="text-blue-200 text-sm opacity-80">Expense and income tracking<\/span><\/div>
        <div class="flex items-center gap-3"><div class="w-5 h-5 rounded-full flex items-center justify-center" style="background:rgba(201,168,76,.2)"><svg width="10" height="10" fill="none" viewBox="0 0 12 12"><path d="M2 6l3 3 5-5" stroke="#c9a84c" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><\/svg><\/div><span class="text-blue-200 text-sm opacity-80">Project management<\/span><\/div>
        <div class="flex items-center gap-3"><div class="w-5 h-5 rounded-full flex items-center justify-center" style="background:rgba(201,168,76,.2)"><svg width="10" height="10" fill="none" viewBox="0 0 12 12"><path d="M2 6l3 3 5-5" stroke="#c9a84c" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><\/svg><\/div><span class="text-blue-200 text-sm opacity-80">Invoice generation<\/span><\/div>
        <div class="flex items-center gap-3"><div class="w-5 h-5 rounded-full flex items-center justify-center" style="background:rgba(201,168,76,.2)"><svg width="10" height="10" fill="none" viewBox="0 0 12 12"><path d="M2 6l3 3 5-5" stroke="#c9a84c" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><\/svg><\/div><span class="text-blue-200 text-sm opacity-80">Financial reports<\/span><\/div>
      <\/div>
    <\/div>
    <p class="relative z-10 text-blue-300 text-xs opacity-40">© 2025 FinanceHub<\/p>
  <\/div>
  <div class="flex-1 flex items-center justify-center px-6 py-10 sm:px-12 overflow-y-auto">
    <div class="w-full max-w-sm">
      <h1 class="text-2xl font-semibold text-slate-800 mb-1">Create account<\/h1>
      <p class="text-slate-400 text-sm mb-6">Fill in your details to get started<\/p>
      {% if form.non_field_errors %}<div class="mb-5 px-4 py-3 rounded-lg bg-red-50 border border-red-200">{% for e in form.non_field_errors %}<p class="text-red-600 text-sm">{{ e }}<\/p>{% endfor %}<\/div>{% endif %}
      <form method="post" novalidate>
        {% csrf_token %}
        <div class="mb-4">
          <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">Full name<\/label>
          <input type="text" name="full_name" value="{{ form.full_name.value|default:'' }}" class="fi {% if form.full_name.errors %}err{% endif %}" placeholder="Jane Doe"/>
          {% if form.full_name.errors %}<p class="text-red-500 text-xs mt-1">{{ form.full_name.errors.0 }}<\/p>{% endif %}
        <\/div>
        <div class="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">Username<\/label>
            <input type="text" name="username" value="{{ form.username.value|default:'' }}" class="fi {% if form.username.errors %}err{% endif %}" placeholder="janedoe"/>
            {% if form.username.errors %}<p class="text-red-500 text-xs mt-1">{{ form.username.errors.0 }}<\/p>{% endif %}
          <\/div>
          <div>
            <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">Email<\/label>
            <input type="email" name="email" value="{{ form.email.value|default:'' }}" class="fi {% if form.email.errors %}err{% endif %}" placeholder="you@co.com"/>
            {% if form.email.errors %}<p class="text-red-500 text-xs mt-1">{{ form.email.errors.0 }}<\/p>{% endif %}
          <\/div>
        <\/div>
        <div class="mb-3">
          <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">Password<\/label>
          <input type="password" name="password" id="p1" class="fi {% if form.password.errors %}err{% endif %}" placeholder="Minimum 8 characters" oninput="pwStr(this.value)" autocomplete="new-password"/>
          <div class="sb grid grid-cols-4 gap-1 mt-1.5"><div id="s1" class="bg-slate-200"><\/div><div id="s2" class="bg-slate-200"><\/div><div id="s3" class="bg-slate-200"><\/div><div id="s4" class="bg-slate-200"><\/div><\/div>
          <p id="slbl" class="text-xs text-slate-400 mt-0.5 h-4"><\/p>
          {% if form.password.errors %}<p class="text-red-500 text-xs mt-1">{{ form.password.errors.0 }}<\/p>{% endif %}
        <\/div>
        <div class="mb-6">
          <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">Confirm password<\/label>
          <input type="password" name="password2" class="fi {% if form.password2.errors %}err{% endif %}" placeholder="Re-enter password" autocomplete="new-password"/>
          {% if form.password2.errors %}<p class="text-red-500 text-xs mt-1">{{ form.password2.errors.0 }}<\/p>{% endif %}
        <\/div>
        <button type="submit" class="w-full py-2.5 rounded-lg text-white font-semibold text-sm" style="background:#0f2044">Create account<\/button>
      <\/form>
      <p class="text-center text-slate-400 text-sm mt-5">Already have an account? <a href="{% url 'accounts:login' %}" class="font-medium" style="color:#0f2044">Sign in<\/a><\/p>
    <\/div>
  <\/div>
<\/body>
<script>
function pwStr(v){
  var c=['#dc2626','#f97316','#eab308','#16a34a'],l=['Weak','Fair','Good','Strong'],s=0;
  if(v.length>=8)s++;if(/[A-Z]/.test(v))s++;if(/[0-9]/.test(v))s++;if(/[^A-Za-z0-9]/.test(v))s++;
  [1,2,3,4].forEach(function(i){document.getElementById('s'+i).style.background=i<=s?c[s-1]:'#e2e8f0';});
  var lbl=document.getElementById('slbl');lbl.textContent=v.length?l[s-1]||'':'';lbl.style.color=s>0?c[s-1]:'#94a3b8';
}
<\/script><\/html>
"""
w("templates/accounts/register.html", REGISTER_HTML)

DASHBOARD_HTML = """
{% extends 'base.html' %}
{% block title %}Dashboard - FinanceHub{% endblock %}
{% block nav_dashboard %}active{% endblock %}
{% block page_title %}Dashboard{% endblock %}
{% block page_sub %}Good to see you, {{ request.user.full_name|default:request.user.username }}{% endblock %}
{% block content %}
<div class="space-y-5">
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <div class="lg:col-span-1 rounded-2xl p-6 text-white relative overflow-hidden" style="background:linear-gradient(135deg,#0f2044 0%,#1e3a5f 100%)">
      <div class="absolute right-0 top-0 w-32 h-32 rounded-full opacity-10" style="background:#c9a84c;transform:translate(30%,-30%)"><\/div>
      <p class="text-blue-200 text-xs font-medium uppercase tracking-wider mb-3">Total Balance<\/p>
      <div class="text-3xl font-bold mb-1">${{ balance|floatformat:2 }}<\/div>
      <p class="text-blue-300 text-xs opacity-70">All-time net<\/p>
      <div class="mt-5 pt-4 border-t border-white/10 flex gap-4 text-xs">
        <div><span class="text-green-300">Income<\/span><span class="text-white font-semibold ml-1">${{ total_income|floatformat:2 }}<\/span><\/div>
        <div><span class="text-red-300">Expense<\/span><span class="text-white font-semibold ml-1">${{ total_expense|floatformat:2 }}<\/span><\/div>
      <\/div>
    <\/div>
    <div class="lg:col-span-2 grid grid-cols-2 gap-4">
      <div class="card border-l-4" style="border-color:#16a34a">
        <div class="flex items-start justify-between">
          <div><p class="text-slate-400 text-xs font-medium uppercase tracking-wide">Total Income<\/p><div class="text-2xl font-bold mt-1" style="color:#16a34a">${{ total_income|floatformat:2 }}<\/div><\/div>
          <div class="w-10 h-10 rounded-xl flex items-center justify-center" style="background:#dcfce7"><svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#16a34a" stroke-width="2"><path stroke-linecap="round" d="M12 19V5m-7 7l7-7 7 7"/><\/svg><\/div>
        <\/div>
        <a href="{% url 'finance:list' %}?type=income" class="text-xs mt-3 block" style="color:#16a34a">View all income &rarr;<\/a>
      <\/div>
      <div class="card border-l-4" style="border-color:#dc2626">
        <div class="flex items-start justify-between">
          <div><p class="text-slate-400 text-xs font-medium uppercase tracking-wide">Total Expenses<\/p><div class="text-2xl font-bold mt-1" style="color:#dc2626">${{ total_expense|floatformat:2 }}<\/div><\/div>
          <div class="w-10 h-10 rounded-xl flex items-center justify-center" style="background:#fee2e2"><svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="#dc2626" stroke-width="2"><path stroke-linecap="round" d="M12 5v14m7-7l-7 7-7-7"/><\/svg><\/div>
        <\/div>
        <a href="{% url 'finance:list' %}?type=expense" class="text-xs mt-3 block" style="color:#dc2626">View all expenses &rarr;<\/a>
      <\/div>
      <div class="card">
        <p class="text-slate-400 text-xs font-medium uppercase tracking-wide">Active Projects<\/p>
        <div class="text-2xl font-bold text-slate-800 mt-1">{{ active_projects }}<\/div>
        <a href="{% url 'projects:list' %}" class="text-xs mt-2 block text-blue-600">Manage projects &rarr;<\/a>
      <\/div>
      <div class="card">
        <p class="text-slate-400 text-xs font-medium uppercase tracking-wide">Pending Invoices<\/p>
        <div class="flex items-end gap-2 mt-1">
          <span class="text-2xl font-bold text-slate-800">{{ pending_invoices }}<\/span>
          {% if overdue_invoices %}<span class="badge badge-red mb-0.5">{{ overdue_invoices }} overdue<\/span>{% endif %}
        <\/div>
        <a href="{% url 'invoices:list' %}" class="text-xs mt-2 block text-blue-600">View invoices &rarr;<\/a>
      <\/div>
    <\/div>
  <\/div>
  <div class="grid grid-cols-1 xl:grid-cols-5 gap-4">
    <div class="card xl:col-span-3">
      <h3 class="font-semibold text-slate-800 text-sm mb-1">Monthly Overview<\/h3>
      <p class="text-slate-400 text-xs mb-4">Income vs expenses - last 6 months<\/p>
      <canvas id="monthlyChart" height="180"><\/canvas>
    <\/div>
    <div class="card xl:col-span-2">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-semibold text-slate-800 text-sm">Recent Transactions<\/h3>
        <a href="{% url 'finance:list' %}" class="text-xs text-blue-600">View all<\/a>
      <\/div>
      {% if recent_txns %}
        <div class="space-y-2.5">
          {% for t in recent_txns %}
            <div class="flex items-center justify-between py-1.5 border-b border-slate-50 last:border-0">
              <div class="flex items-center gap-2.5 min-w-0">
                <div class="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 {% if t.type == 'income' %}bg-green-50{% else %}bg-red-50{% endif %}">
                  {% if t.type == 'income' %}<svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="#16a34a" stroke-width="2.5"><path stroke-linecap="round" d="M12 19V5m-5 5l5-5 5 5"/><\/svg>
                  {% else %}<svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="#dc2626" stroke-width="2.5"><path stroke-linecap="round" d="M12 5v14m-5-5l5 5 5-5"/><\/svg>{% endif %}
                <\/div>
                <div class="min-w-0">
                  <p class="text-slate-700 text-xs font-medium truncate">{{ t.description|default:t.get_type_display }}<\/p>
                  <p class="text-slate-400 text-xs">{{ t.date|date:"M d" }}{% if t.category %} &middot; {{ t.category.name }}{% endif %}<\/p>
                <\/div>
              <\/div>
              <span class="text-xs font-semibold flex-shrink-0 ml-3 {% if t.type == 'income' %}text-green-600{% else %}text-red-500{% endif %}">{% if t.type == 'income' %}+{% else %}-{% endif %}${{ t.amount|floatformat:2 }}<\/span>
            <\/div>
          {% endfor %}
        <\/div>
      {% else %}
        <p class="text-slate-400 text-sm text-center py-8">No transactions yet<\/p>
      {% endif %}
    <\/div>
  <\/div>
<\/div>
{% endblock %}
{% block scripts %}
<script>
var raw = {{ chart_data|safe }};
new Chart(document.getElementById('monthlyChart'), {
  type: 'bar',
  data: {
    labels: raw.map(function(d){return d.month;}),
    datasets: [
      {label:'Income', data:raw.map(function(d){return d.income;}), backgroundColor:'rgba(22,163,74,.15)', borderColor:'#16a34a', borderWidth:2, borderRadius:4},
      {label:'Expense',data:raw.map(function(d){return d.expense;}),backgroundColor:'rgba(220,38,38,.1)',  borderColor:'#dc2626', borderWidth:2, borderRadius:4}
    ]
  },
  options:{responsive:true,maintainAspectRatio:true,plugins:{legend:{labels:{font:{size:11},boxWidth:12}}},scales:{x:{grid:{display:false},ticks:{font:{size:11}}},y:{grid:{color:'#f1f5f9'},ticks:{font:{size:11},callback:function(v){return '$'+v;}}}}}
});
<\/script>
{% endblock %}
"""
w("templates/dashboard/index.html", DASHBOARD_HTML)

FINANCE_LIST = """
{% extends 'base.html' %}
{% block title %}Finance - FinanceHub{% endblock %}
{% block nav_finance %}active{% endblock %}
{% block page_title %}Finance Tracker{% endblock %}
{% block page_sub %}Income and expense management{% endblock %}
{% block header_actions %}
  <a href="{% url 'finance:add' %}" class="btn btn-navy">+ Add Transaction<\/a>
  <a href="{% url 'finance:categories' %}" class="btn btn-outline">Categories<\/a>
{% endblock %}
{% block content %}
<div class="space-y-4">
  <div class="grid grid-cols-3 gap-3">
    <div class="card text-center py-3"><p class="text-xs text-slate-400 uppercase tracking-wide font-medium">Balance<\/p><p class="text-xl font-bold mt-1 {% if balance >= 0 %}text-slate-800{% else %}text-red-600{% endif %}">${{ balance|floatformat:2 }}<\/p><\/div>
    <div class="card text-center py-3"><p class="text-xs text-slate-400 uppercase tracking-wide font-medium">Income<\/p><p class="text-xl font-bold mt-1 text-green-600">${{ total_income|floatformat:2 }}<\/p><\/div>
    <div class="card text-center py-3"><p class="text-xs text-slate-400 uppercase tracking-wide font-medium">Expenses<\/p><p class="text-xl font-bold mt-1 text-red-500">${{ total_expense|floatformat:2 }}<\/p><\/div>
  <\/div>
  <div class="card">
    <form method="get" class="flex flex-wrap gap-3 items-end">
      <div><label class="block text-slate-500 text-xs mb-1 uppercase tracking-wide font-medium">Type<\/label><select name="type" class="form-input w-32"><option value="">All<\/option><option value="income" {% if filters.type == 'income' %}selected{% endif %}>Income<\/option><option value="expense" {% if filters.type == 'expense' %}selected{% endif %}>Expense<\/option><\/select><\/div>
      <div><label class="block text-slate-500 text-xs mb-1 uppercase tracking-wide font-medium">Category<\/label><select name="category" class="form-input w-40"><option value="">All categories<\/option>{% for cat in categories %}<option value="{{ cat.pk }}" {% if filters.category == cat.pk|stringformat:'s' %}selected{% endif %}>{{ cat.name }}<\/option>{% endfor %}<\/select><\/div>
      <div><label class="block text-slate-500 text-xs mb-1 uppercase tracking-wide font-medium">Month<\/label><input type="month" name="month" value="{{ filters.month }}" class="form-input w-40"/><\/div>
      <button type="submit" class="btn btn-navy">Filter<\/button>
      <a href="{% url 'finance:list' %}" class="btn btn-outline">Clear<\/a>
    <\/form>
  <\/div>
  <div class="card p-0 overflow-hidden">
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead><tr class="bg-slate-50 border-b border-slate-100">
          <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Date<\/th>
          <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Description<\/th>
          <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Category<\/th>
          <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Type<\/th>
          <th class="text-right px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Amount<\/th>
          <th class="px-5 py-3"><\/th>
        <\/tr><\/thead>
        <tbody>
          {% for t in transactions %}
          <tr class="table-row border-b border-slate-50">
            <td class="px-5 py-3 text-slate-500 text-xs">{{ t.date|date:"M d, Y" }}<\/td>
            <td class="px-5 py-3"><p class="text-slate-700 font-medium text-sm">{{ t.description|default:"—" }}<\/p>{% if t.reference %}<p class="text-slate-400 text-xs">Ref: {{ t.reference }}<\/p>{% endif %}<\/td>
            <td class="px-5 py-3">{% if t.category %}<span class="badge badge-slate">{{ t.category.name }}<\/span>{% else %}<span class="text-slate-300 text-xs">—<\/span>{% endif %}<\/td>
            <td class="px-5 py-3">{% if t.type == 'income' %}<span class="badge badge-green">Income<\/span>{% else %}<span class="badge badge-red">Expense<\/span>{% endif %}<\/td>
            <td class="px-5 py-3 text-right font-semibold {% if t.type == 'income' %}text-green-600{% else %}text-red-500{% endif %}">{% if t.type == 'income' %}+{% else %}-{% endif %}${{ t.amount|floatformat:2 }}<\/td>
            <td class="px-5 py-3 text-right">
              <a href="{% url 'finance:edit' t.pk %}" class="text-blue-500 hover:text-blue-700 text-xs font-medium">Edit<\/a>
              <form method="post" action="{% url 'finance:delete' t.pk %}" onsubmit="return confirm('Delete?')" style="display:inline;margin-left:.5rem">{% csrf_token %}<button class="text-red-400 hover:text-red-600 text-xs font-medium">Delete<\/button><\/form>
            <\/td>
          <\/tr>
          {% empty %}<tr><td colspan="6" class="px-5 py-12 text-center text-slate-400 text-sm">No transactions. <a href="{% url 'finance:add' %}" class="text-blue-600">Add your first &rarr;<\/a><\/td><\/tr>{% endfor %}
        <\/tbody>
      <\/table>
    <\/div>
  <\/div>
<\/div>
{% endblock %}
"""
w("templates/finance/list.html", FINANCE_LIST)

FINANCE_FORM = """
{% extends 'base.html' %}
{% block title %}{{ title }} - FinanceHub{% endblock %}
{% block nav_finance %}active{% endblock %}
{% block page_title %}{{ title }}{% endblock %}
{% block content %}
<div class="max-w-lg"><div class="card">
  <form method="post" novalidate>{% csrf_token %}
    {% for field in form %}
      <div class="mb-4">
        <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">{{ field.label }}<\/label>
        {{ field }}
        {% if field.errors %}<p class="text-red-500 text-xs mt-1">{{ field.errors.0 }}<\/p>{% endif %}
      <\/div>
    {% endfor %}
    <div class="flex gap-3 mt-6">
      <button type="submit" class="btn btn-navy">{% if obj %}Save changes{% else %}Add transaction{% endif %}<\/button>
      <a href="{% url 'finance:list' %}" class="btn btn-outline">Cancel<\/a>
    <\/div>
  <\/form>
<\/div><\/div>
{% endblock %}
"""
w("templates/finance/form.html", FINANCE_FORM)

FINANCE_CATS = """
{% extends 'base.html' %}
{% block title %}Categories - FinanceHub{% endblock %}
{% block nav_finance %}active{% endblock %}
{% block page_title %}Categories{% endblock %}
{% block header_actions %}<a href="{% url 'finance:list' %}" class="btn btn-outline">&larr; Back<\/a>{% endblock %}
{% block content %}
<div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
  <div class="lg:col-span-2 card p-0 overflow-hidden">
    <table class="w-full text-sm">
      <thead><tr class="bg-slate-50 border-b border-slate-100">
        <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Name<\/th>
        <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Type<\/th>
        <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Color<\/th>
        <th class="px-5 py-3"><\/th>
      <\/tr><\/thead>
      <tbody>{% for cat in categories %}
        <tr class="table-row border-b border-slate-50">
          <td class="px-5 py-3 font-medium text-slate-700">{{ cat.name }}<\/td>
          <td class="px-5 py-3">{% if cat.type == 'income' %}<span class="badge badge-green">Income<\/span>{% else %}<span class="badge badge-red">Expense<\/span>{% endif %}<\/td>
          <td class="px-5 py-3"><div class="w-5 h-5 rounded-full" style="background:{{ cat.color }}"><\/div><\/td>
          <td class="px-5 py-3 text-right"><form method="post" action="{% url 'finance:delete_category' cat.pk %}" onsubmit="return confirm('Delete?')">{% csrf_token %}<button class="text-red-400 hover:text-red-600 text-xs font-medium">Delete<\/button><\/form><\/td>
        <\/tr>
      {% empty %}<tr><td colspan="4" class="px-5 py-10 text-center text-slate-400 text-sm">No categories.<\/td><\/tr>{% endfor %}<\/tbody>
    <\/table>
  <\/div>
  <div class="card"><h3 class="font-semibold text-slate-700 text-sm mb-4">Add Category<\/h3>
    <form method="post" novalidate>{% csrf_token %}
      {% for field in form %}<div class="mb-4"><label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">{{ field.label }}<\/label>{{ field }}{% if field.errors %}<p class="text-red-500 text-xs mt-1">{{ field.errors.0 }}<\/p>{% endif %}<\/div>{% endfor %}
      <button type="submit" class="btn btn-navy w-full">Add Category<\/button>
    <\/form>
  <\/div>
<\/div>
{% endblock %}
"""
w("templates/finance/categories.html", FINANCE_CATS)

PROJ_LIST = """
{% extends 'base.html' %}
{% block title %}Projects - FinanceHub{% endblock %}
{% block nav_projects %}active{% endblock %}
{% block page_title %}Projects{% endblock %}
{% block page_sub %}Track and manage your work{% endblock %}
{% block header_actions %}<a href="{% url 'projects:add' %}" class="btn btn-navy">+ New Project<\/a>{% endblock %}
{% block content %}
<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
  {% for p in projects %}
  <div class="card hover:shadow-md transition-shadow">
    <div class="flex items-start justify-between mb-3">
      <div class="min-w-0"><a href="{% url 'projects:detail' p.pk %}" class="font-semibold text-slate-800 hover:text-blue-700 block truncate">{{ p.name }}<\/a>{% if p.client %}<p class="text-slate-400 text-xs mt-0.5 truncate">{{ p.client.name }}<\/p>{% endif %}<\/div>
      {% if p.status == 'active' %}<span class="badge badge-green ml-2 flex-shrink-0">Active<\/span>{% elif p.status == 'completed' %}<span class="badge badge-blue ml-2 flex-shrink-0">Done<\/span>{% elif p.status == 'on_hold' %}<span class="badge badge-yellow ml-2 flex-shrink-0">On Hold<\/span>{% else %}<span class="badge badge-slate ml-2 flex-shrink-0">{{ p.get_status_display }}<\/span>{% endif %}
    <\/div>
    {% if p.description %}<p class="text-slate-500 text-xs mb-3">{{ p.description|truncatechars:80 }}<\/p>{% endif %}
    <div class="mb-3">
      <div class="flex justify-between text-xs text-slate-400 mb-1"><span>{{ p.tasks.count }} task{{ p.tasks.count|pluralize }}<\/span><span>{{ p.task_progress }}% done<\/span><\/div>
      <div class="h-1.5 bg-slate-100 rounded-full overflow-hidden"><div class="h-full rounded-full" style="width:{{ p.task_progress }}%;background:#0f2044"><\/div><\/div>
    <\/div>
    <div class="flex items-center justify-between text-xs text-slate-400">
      <span>{% if p.due_date %}Due {{ p.due_date|date:"M d, Y" }}{% else %}No deadline{% endif %}<\/span>
      {% if p.budget %}<span>${{ p.budget|floatformat:0 }} budget<\/span>{% endif %}
    <\/div>
  <\/div>
  {% empty %}<div class="md:col-span-3 card text-center py-16"><p class="text-slate-400 text-sm mb-3">No projects yet.<\/p><a href="{% url 'projects:add' %}" class="btn btn-navy inline-flex">Create first project<\/a><\/div>{% endfor %}
<\/div>
{% endblock %}
"""
w("templates/projects/list.html", PROJ_LIST)

PROJ_DETAIL = """
{% extends 'base.html' %}
{% block title %}{{ project.name }} - FinanceHub{% endblock %}
{% block nav_projects %}active{% endblock %}
{% block page_title %}{{ project.name }}{% endblock %}
{% block page_sub %}{% if project.client %}{{ project.client.name }}{% endif %}{% endblock %}
{% block header_actions %}
  <a href="{% url 'projects:edit' project.pk %}" class="btn btn-outline">Edit<\/a>
  <form method="post" action="{% url 'projects:delete' project.pk %}" onsubmit="return confirm('Delete project?')" style="display:inline">{% csrf_token %}<button class="btn btn-danger">Delete<\/button><\/form>
{% endblock %}
{% block content %}
<div class="grid grid-cols-1 xl:grid-cols-3 gap-5">
  <div class="xl:col-span-2 space-y-4">
    <div class="card">
      <div class="flex items-center justify-between mb-2"><h3 class="font-semibold text-slate-700 text-sm">Progress<\/h3><span class="text-sm font-bold text-slate-800">{{ project.task_progress }}%<\/span><\/div>
      <div class="h-2 bg-slate-100 rounded-full overflow-hidden"><div class="h-full rounded-full" style="width:{{ project.task_progress }}%;background:linear-gradient(90deg,#0f2044,#2a4a7f)"><\/div><\/div>
    <\/div>
    <div class="card">
      <h3 class="font-semibold text-slate-700 text-sm mb-3">Add Task<\/h3>
      <form method="post" action="{% url 'projects:add_task' project.pk %}" novalidate>{% csrf_token %}
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
          {% for field in task_form %}<div class="{% if forloop.first %}sm:col-span-2{% endif %}"><label class="block text-slate-400 text-xs mb-1">{{ field.label }}<\/label>{{ field }}<\/div>{% endfor %}
        <\/div>
        <button type="submit" class="btn btn-navy">Add Task<\/button>
      <\/form>
    <\/div>
    <div class="card p-0 overflow-hidden">
      <div class="px-5 py-3.5 border-b border-slate-100 font-semibold text-slate-700 text-sm">Tasks<\/div>
      {% for task in tasks %}
      <div class="flex items-center gap-3 px-5 py-3 border-b border-slate-50 hover:bg-slate-50 last:border-0">
        <div class="flex-1 min-w-0">
          <p class="text-slate-700 text-sm font-medium {% if task.status == 'done' %}line-through text-slate-400{% endif %}">{{ task.title }}<\/p>
          <div class="flex gap-3 mt-0.5 text-xs text-slate-400">
            {% if task.assigned_to %}<span>{{ task.assigned_to.full_name|default:task.assigned_to.username }}<\/span>{% endif %}
            {% if task.due_date %}<span>Due {{ task.due_date|date:"M d" }}<\/span>{% endif %}
            {% if task.priority == 'high' %}<span class="text-red-500 font-medium">High<\/span>{% elif task.priority == 'medium' %}<span class="text-yellow-600">Medium<\/span>{% endif %}
          <\/div>
        <\/div>
        <form method="post" action="{% url 'projects:task_status' task.pk %}">{% csrf_token %}
          <select name="status" onchange="this.form.submit()" class="text-xs border border-slate-200 rounded-lg px-2 py-1 bg-white cursor-pointer outline-none">
            {% for val, lbl in task.STATUS %}<option value="{{ val }}" {% if task.status == val %}selected{% endif %}>{{ lbl }}<\/option>{% endfor %}
          <\/select>
        <\/form>
        <form method="post" action="{% url 'projects:delete_task' task.pk %}" onsubmit="return confirm('Remove?')">{% csrf_token %}<button class="text-red-400 hover:text-red-600 text-xs">&#x2715;<\/button><\/form>
      <\/div>
      {% empty %}<p class="px-5 py-8 text-center text-slate-400 text-sm">No tasks yet.<\/p>{% endfor %}
    <\/div>
  <\/div>
  <div class="space-y-4">
    <div class="card">
      <h3 class="font-semibold text-slate-700 text-sm mb-4">Project Details<\/h3>
      <dl class="space-y-3 text-sm">
        <div class="flex justify-between"><dt class="text-slate-400">Status<\/dt><dd>{% if project.status == 'active' %}<span class="badge badge-green">Active<\/span>{% elif project.status == 'completed' %}<span class="badge badge-blue">Done<\/span>{% else %}<span class="badge badge-slate">{{ project.get_status_display }}<\/span>{% endif %}<\/dd><\/div>
        {% if project.client %}<div class="flex justify-between"><dt class="text-slate-400">Client<\/dt><dd class="font-medium"><a href="{% url 'clients:detail' project.client.pk %}" class="hover:text-blue-600">{{ project.client.name }}<\/a><\/dd><\/div>{% endif %}
        <div class="flex justify-between"><dt class="text-slate-400">Owner<\/dt><dd class="font-medium text-slate-700">{{ project.owner.full_name|default:project.owner.username }}<\/dd><\/div>
        <div class="flex justify-between"><dt class="text-slate-400">Start<\/dt><dd class="font-medium text-slate-700">{{ project.start_date|date:"M d, Y" }}<\/dd><\/div>
        {% if project.due_date %}<div class="flex justify-between"><dt class="text-slate-400">Due<\/dt><dd class="font-medium text-slate-700">{{ project.due_date|date:"M d, Y" }}<\/dd><\/div>{% endif %}
        {% if project.budget %}<div class="flex justify-between"><dt class="text-slate-400">Budget<\/dt><dd class="font-semibold text-slate-800">${{ project.budget|floatformat:2 }}<\/dd><\/div>{% endif %}
      <\/dl>
    <\/div>
    {% if project.description %}<div class="card"><h3 class="font-semibold text-slate-700 text-sm mb-2">Description<\/h3><p class="text-slate-500 text-sm leading-relaxed">{{ project.description }}<\/p><\/div>{% endif %}
  <\/div>
<\/div>
{% endblock %}
"""
w("templates/projects/detail.html", PROJ_DETAIL)

PROJ_FORM = """
{% extends 'base.html' %}
{% block title %}{{ title }} - FinanceHub{% endblock %}
{% block nav_projects %}active{% endblock %}
{% block page_title %}{{ title }}{% endblock %}
{% block content %}
<div class="max-w-2xl"><div class="card">
  <form method="post" novalidate>{% csrf_token %}
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {% for field in form %}
        <div class="{% if field.name == 'description' or field.name == 'name' %}sm:col-span-2{% endif %}">
          <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">{{ field.label }}<\/label>
          {{ field }}{% if field.errors %}<p class="text-red-500 text-xs mt-1">{{ field.errors.0 }}<\/p>{% endif %}
        <\/div>
      {% endfor %}
    <\/div>
    <div class="flex gap-3 mt-6"><button type="submit" class="btn btn-navy">{% if obj %}Save changes{% else %}Create project{% endif %}<\/button><a href="{% url 'projects:list' %}" class="btn btn-outline">Cancel<\/a><\/div>
  <\/form>
<\/div><\/div>
{% endblock %}
"""
w("templates/projects/form.html", PROJ_FORM)

CLIENTS_LIST = """
{% extends 'base.html' %}
{% block title %}Clients - FinanceHub{% endblock %}
{% block nav_clients %}active{% endblock %}
{% block page_title %}Clients{% endblock %}
{% block page_sub %}Your client directory{% endblock %}
{% block header_actions %}<a href="{% url 'clients:add' %}" class="btn btn-navy">+ Add Client<\/a>{% endblock %}
{% block content %}
<div class="space-y-4">
  <div class="card"><form method="get" class="flex gap-3"><input type="text" name="q" value="{{ q }}" class="form-input max-w-xs" placeholder="Search by name, company, email..."/><button type="submit" class="btn btn-navy">Search<\/button>{% if q %}<a href="{% url 'clients:list' %}" class="btn btn-outline">Clear<\/a>{% endif %}<\/form><\/div>
  <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
    {% for c in clients %}
    <div class="card hover:shadow-md transition-shadow">
      <div class="flex items-start gap-3">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold text-sm flex-shrink-0" style="background:#1e3a5f">{{ c.name|first|upper }}<\/div>
        <div class="flex-1 min-w-0"><a href="{% url 'clients:detail' c.pk %}" class="font-semibold text-slate-800 hover:text-blue-700 block truncate">{{ c.name }}<\/a>{% if c.company %}<p class="text-slate-400 text-xs truncate">{{ c.company }}<\/p>{% endif %}<\/div>
      <\/div>
      <div class="mt-3 space-y-1.5 text-xs text-slate-500">
        {% if c.email %}<div>{{ c.email }}<\/div>{% endif %}
        {% if c.phone %}<div>{{ c.phone }}<\/div>{% endif %}
      <\/div>
      <div class="mt-3 flex gap-2 text-xs"><a href="{% url 'clients:detail' c.pk %}" class="text-blue-600">View<\/a><a href="{% url 'clients:edit' c.pk %}" class="text-slate-500">Edit<\/a><\/div>
    <\/div>
    {% empty %}<div class="md:col-span-3 card text-center py-16"><p class="text-slate-400 text-sm mb-3">{% if q %}No clients match.{% else %}No clients yet.{% endif %}<\/p><a href="{% url 'clients:add' %}" class="btn btn-navy inline-flex">Add first client<\/a><\/div>{% endfor %}
  <\/div>
<\/div>
{% endblock %}
"""
w("templates/clients/list.html", CLIENTS_LIST)

CLIENTS_DETAIL = """
{% extends 'base.html' %}
{% block title %}{{ client.name }} - FinanceHub{% endblock %}
{% block nav_clients %}active{% endblock %}
{% block page_title %}{{ client.name }}{% endblock %}
{% block page_sub %}{% if client.company %}{{ client.company }}{% endif %}{% endblock %}
{% block header_actions %}
  <a href="{% url 'clients:edit' client.pk %}" class="btn btn-outline">Edit<\/a>
  <form method="post" action="{% url 'clients:delete' client.pk %}" onsubmit="return confirm('Delete client?')" style="display:inline">{% csrf_token %}<button class="btn btn-danger">Delete<\/button><\/form>
{% endblock %}
{% block content %}
<div class="grid grid-cols-1 xl:grid-cols-3 gap-5">
  <div class="card">
    <div class="flex items-center gap-4 mb-5">
      <div class="w-14 h-14 rounded-2xl flex items-center justify-center text-white text-xl font-bold" style="background:#0f2044">{{ client.name|first|upper }}<\/div>
      <div><h2 class="font-semibold text-slate-800">{{ client.name }}<\/h2>{% if client.company %}<p class="text-slate-400 text-sm">{{ client.company }}<\/p>{% endif %}<\/div>
    <\/div>
    <dl class="space-y-3 text-sm">
      {% if client.email %}<div class="flex gap-3"><dt class="text-slate-400 w-16 flex-shrink-0">Email<\/dt><dd class="text-slate-700">{{ client.email }}<\/dd><\/div>{% endif %}
      {% if client.phone %}<div class="flex gap-3"><dt class="text-slate-400 w-16 flex-shrink-0">Phone<\/dt><dd class="text-slate-700">{{ client.phone }}<\/dd><\/div>{% endif %}
      {% if client.website %}<div class="flex gap-3"><dt class="text-slate-400 w-16 flex-shrink-0">Website<\/dt><dd><a href="{{ client.website }}" target="_blank" class="text-blue-600 hover:underline">{{ client.website }}<\/a><\/dd><\/div>{% endif %}
      {% if client.address %}<div class="flex gap-3"><dt class="text-slate-400 w-16 flex-shrink-0">Address<\/dt><dd class="text-slate-700 whitespace-pre-line">{{ client.address }}<\/dd><\/div>{% endif %}
      {% if client.notes %}<div class="flex gap-3"><dt class="text-slate-400 w-16 flex-shrink-0">Notes<\/dt><dd class="text-slate-500 italic">{{ client.notes }}<\/dd><\/div>{% endif %}
    <\/dl>
  <\/div>
  <div class="xl:col-span-2">
    <div class="card">
      <div class="flex items-center justify-between mb-4"><h3 class="font-semibold text-slate-700 text-sm">Linked Projects<\/h3><a href="{% url 'projects:add' %}" class="btn btn-outline text-xs py-1">+ New Project<\/a><\/div>
      {% if projects %}
        <div class="space-y-2">
          {% for p in projects %}
          <div class="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
            <div><a href="{% url 'projects:detail' p.pk %}" class="font-medium text-slate-700 hover:text-blue-600 text-sm">{{ p.name }}<\/a><p class="text-slate-400 text-xs mt-0.5">{{ p.task_progress }}% complete<\/p><\/div>
            {% if p.status == 'active' %}<span class="badge badge-green">Active<\/span>{% elif p.status == 'completed' %}<span class="badge badge-blue">Done<\/span>{% else %}<span class="badge badge-slate">{{ p.get_status_display }}<\/span>{% endif %}
          <\/div>
          {% endfor %}
        <\/div>
      {% else %}<p class="text-slate-400 text-sm">No projects linked.<\/p>{% endif %}
    <\/div>
  <\/div>
<\/div>
{% endblock %}
"""
w("templates/clients/detail.html", CLIENTS_DETAIL)

CLIENTS_FORM = """
{% extends 'base.html' %}
{% block title %}{{ title }} - FinanceHub{% endblock %}
{% block nav_clients %}active{% endblock %}
{% block page_title %}{{ title }}{% endblock %}
{% block content %}
<div class="max-w-2xl"><div class="card">
  <form method="post" novalidate>{% csrf_token %}
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {% for field in form %}
        <div class="{% if field.name == 'address' or field.name == 'notes' or field.name == 'website' %}sm:col-span-2{% endif %}">
          <label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">{{ field.label }}<\/label>
          {{ field }}{% if field.errors %}<p class="text-red-500 text-xs mt-1">{{ field.errors.0 }}<\/p>{% endif %}
        <\/div>
      {% endfor %}
    <\/div>
    <div class="flex gap-3 mt-6"><button type="submit" class="btn btn-navy">{% if obj %}Save changes{% else %}Add client{% endif %}<\/button><a href="{% url 'clients:list' %}" class="btn btn-outline">Cancel<\/a><\/div>
  <\/form>
<\/div><\/div>
{% endblock %}
"""
w("templates/clients/form.html", CLIENTS_FORM)

INV_LIST = """
{% extends 'base.html' %}
{% block title %}Invoices - FinanceHub{% endblock %}
{% block nav_invoices %}active{% endblock %}
{% block page_title %}Invoices{% endblock %}
{% block page_sub %}Billing and payment tracking{% endblock %}
{% block header_actions %}<a href="{% url 'invoices:add' %}" class="btn btn-navy">+ New Invoice<\/a>{% endblock %}
{% block content %}
<div class="space-y-4">
  <div class="flex flex-wrap gap-2">
    <a href="{% url 'invoices:list' %}" class="btn {% if not status_filter %}btn-navy{% else %}btn-outline{% endif %}">All<\/a>
    <a href="?status=draft"   class="btn {% if status_filter == 'draft'   %}btn-navy{% else %}btn-outline{% endif %}">Draft<\/a>
    <a href="?status=sent"    class="btn {% if status_filter == 'sent'    %}btn-navy{% else %}btn-outline{% endif %}">Sent<\/a>
    <a href="?status=paid"    class="btn {% if status_filter == 'paid'    %}btn-navy{% else %}btn-outline{% endif %}">Paid<\/a>
    <a href="?status=overdue" class="btn {% if status_filter == 'overdue' %}btn-navy{% else %}btn-outline{% endif %}">Overdue<\/a>
  <\/div>
  <div class="card p-0 overflow-hidden"><div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead><tr class="bg-slate-50 border-b border-slate-100">
        <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Invoice #<\/th>
        <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Client<\/th>
        <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Status<\/th>
        <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Issue Date<\/th>
        <th class="text-left px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Due Date<\/th>
        <th class="text-right px-5 py-3 text-slate-500 text-xs font-semibold uppercase tracking-wide">Total<\/th>
        <th class="px-5 py-3"><\/th>
      <\/tr><\/thead>
      <tbody>
        {% for inv in invoices %}
        <tr class="table-row border-b border-slate-50">
          <td class="px-5 py-3"><a href="{% url 'invoices:detail' inv.pk %}" class="font-semibold text-blue-600 hover:underline">{{ inv.invoice_number }}<\/a><\/td>
          <td class="px-5 py-3 text-slate-700 font-medium">{{ inv.client.name }}<\/td>
          <td class="px-5 py-3">{% if inv.status == 'paid' %}<span class="badge badge-green">Paid<\/span>{% elif inv.status == 'overdue' %}<span class="badge badge-red">Overdue<\/span>{% elif inv.status == 'sent' %}<span class="badge badge-blue">Sent<\/span>{% else %}<span class="badge badge-slate">Draft<\/span>{% endif %}<\/td>
          <td class="px-5 py-3 text-slate-500 text-xs">{{ inv.issue_date|date:"M d, Y" }}<\/td>
          <td class="px-5 py-3 text-slate-500 text-xs">{{ inv.due_date|date:"M d, Y" }}<\/td>
          <td class="px-5 py-3 text-right font-semibold text-slate-800">${{ inv.total|floatformat:2 }}<\/td>
          <td class="px-5 py-3"><div class="flex justify-end gap-2">
            <a href="{% url 'invoices:edit' inv.pk %}" class="text-blue-500 text-xs">Edit<\/a>
            <form method="post" action="{% url 'invoices:delete' inv.pk %}" onsubmit="return confirm('Delete?')">{% csrf_token %}<button class="text-red-400 text-xs">Delete<\/button><\/form>
          <\/div><\/td>
        <\/tr>
        {% empty %}<tr><td colspan="7" class="px-5 py-12 text-center text-slate-400 text-sm">No invoices. <a href="{% url 'invoices:add' %}" class="text-blue-600">Create one &rarr;<\/a><\/td><\/tr>{% endfor %}
      <\/tbody>
    <\/table>
  <\/div><\/div>
<\/div>
{% endblock %}
"""
w("templates/invoices/list.html", INV_LIST)

INV_DETAIL = """
{% extends 'base.html' %}
{% block title %}{{ invoice.invoice_number }} - FinanceHub{% endblock %}
{% block nav_invoices %}active{% endblock %}
{% block page_title %}{{ invoice.invoice_number }}{% endblock %}
{% block page_sub %}{{ invoice.client.name }}{% endblock %}
{% block header_actions %}
  {% if invoice.status != 'paid' %}<form method="post" action="{% url 'invoices:mark_paid' invoice.pk %}" style="display:inline">{% csrf_token %}<button class="btn btn-success">Mark as Paid<\/button><\/form>{% endif %}
  <a href="{% url 'invoices:edit' invoice.pk %}" class="btn btn-outline">Edit<\/a>
{% endblock %}
{% block content %}
<div class="max-w-3xl"><div class="card">
  <div class="flex items-start justify-between mb-8 pb-6 border-b border-slate-100">
    <div>
      <div class="flex items-center gap-2 mb-1"><h2 class="text-xl font-bold text-slate-800">{{ invoice.invoice_number }}<\/h2>{% if invoice.status == 'paid' %}<span class="badge badge-green">Paid<\/span>{% elif invoice.status == 'overdue' %}<span class="badge badge-red">Overdue<\/span>{% elif invoice.status == 'sent' %}<span class="badge badge-blue">Sent<\/span>{% else %}<span class="badge badge-slate">Draft<\/span>{% endif %}<\/div>
      <p class="text-slate-400 text-sm">Issued {{ invoice.issue_date|date:"M d, Y" }} &middot; Due {{ invoice.due_date|date:"M d, Y" }}<\/p>
    <\/div>
    <div class="text-right"><p class="text-slate-400 text-xs uppercase tracking-wide">Total Due<\/p><p class="text-3xl font-bold text-slate-800">${{ invoice.total|floatformat:2 }}<\/p><\/div>
  <\/div>
  <div class="mb-6">
    <p class="text-slate-400 text-xs uppercase tracking-wide font-medium mb-1">Bill to<\/p>
    <p class="font-semibold text-slate-800">{{ invoice.client.name }}<\/p>
    {% if invoice.client.company %}<p class="text-slate-500 text-sm">{{ invoice.client.company }}<\/p>{% endif %}
    {% if invoice.client.email %}<p class="text-slate-500 text-sm">{{ invoice.client.email }}<\/p>{% endif %}
  <\/div>
  <table class="w-full text-sm mb-4">
    <thead><tr class="bg-slate-50 rounded-lg">
      <th class="text-left px-4 py-2.5 text-slate-500 text-xs font-semibold uppercase tracking-wide rounded-l-lg">Description<\/th>
      <th class="text-right px-4 py-2.5 text-slate-500 text-xs font-semibold uppercase tracking-wide">Qty<\/th>
      <th class="text-right px-4 py-2.5 text-slate-500 text-xs font-semibold uppercase tracking-wide">Rate<\/th>
      <th class="text-right px-4 py-2.5 text-slate-500 text-xs font-semibold uppercase tracking-wide rounded-r-lg">Total<\/th>
    <\/tr><\/thead>
    <tbody>{% for item in invoice.items.all %}
      <tr class="border-b border-slate-50">
        <td class="px-4 py-3 text-slate-700">{{ item.description }}<\/td>
        <td class="px-4 py-3 text-right text-slate-500">{{ item.quantity }}<\/td>
        <td class="px-4 py-3 text-right text-slate-500">${{ item.rate|floatformat:2 }}<\/td>
        <td class="px-4 py-3 text-right font-medium text-slate-800">${{ item.line_total|floatformat:2 }}<\/td>
      <\/tr>
    {% endfor %}<\/tbody>
  <\/table>
  <div class="flex justify-end"><div class="w-56 space-y-1.5 text-sm">
    <div class="flex justify-between text-slate-500"><span>Subtotal<\/span><span>${{ invoice.subtotal|floatformat:2 }}<\/span><\/div>
    {% if invoice.tax_rate %}<div class="flex justify-between text-slate-500"><span>Tax ({{ invoice.tax_rate }}%)<\/span><span>${{ invoice.tax_amount|floatformat:2 }}<\/span><\/div>{% endif %}
    <div class="flex justify-between font-bold text-slate-800 pt-2 border-t border-slate-200 text-base"><span>Total<\/span><span>${{ invoice.total|floatformat:2 }}<\/span><\/div>
  <\/div><\/div>
  {% if invoice.notes %}<div class="mt-6 pt-5 border-t border-slate-100"><p class="text-slate-400 text-xs uppercase tracking-wide font-medium mb-1">Notes<\/p><p class="text-slate-600 text-sm">{{ invoice.notes }}<\/p><\/div>{% endif %}
<\/div><\/div>
{% endblock %}
"""
w("templates/invoices/detail.html", INV_DETAIL)

INV_FORM = """
{% extends 'base.html' %}
{% block title %}{{ title }} - FinanceHub{% endblock %}
{% block nav_invoices %}active{% endblock %}
{% block page_title %}{{ title }}{% endblock %}
{% block content %}
<div class="max-w-3xl">
  <form method="post" novalidate>{% csrf_token %}
    <div class="card mb-4">
      <h3 class="font-semibold text-slate-700 text-sm mb-4">Invoice Details<\/h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {% for field in form %}<div class="{% if field.name == 'notes' %}sm:col-span-2{% endif %}"><label class="block text-slate-500 text-xs font-medium uppercase tracking-wide mb-1.5">{{ field.label }}<\/label>{{ field }}{% if field.errors %}<p class="text-red-500 text-xs mt-1">{{ field.errors.0 }}<\/p>{% endif %}<\/div>{% endfor %}
      <\/div>
    <\/div>
    <div class="card mb-4">
      <h3 class="font-semibold text-slate-700 text-sm mb-4">Line Items<\/h3>
      {{ formset.management_form }}
      <table class="w-full text-sm mb-3">
        <thead><tr class="text-slate-400 text-xs"><th class="text-left pb-2 font-medium">Description<\/th><th class="text-left pb-2 font-medium w-24">Qty<\/th><th class="text-left pb-2 font-medium w-28">Rate<\/th><th class="pb-2 w-8"><\/th><\/tr><\/thead>
        <tbody>{% for item_form in formset %}
          <tr><td class="pr-3 pb-2">{{ item_form.description }}<\/td><td class="pr-3 pb-2">{{ item_form.quantity }}<\/td><td class="pr-3 pb-2">{{ item_form.rate }}<\/td><td class="pb-2">{% if item_form.instance.pk %}{{ item_form.DELETE }}{% endif %}<\/td>
          {% for hidden in item_form.hidden_fields %}{{ hidden }}{% endfor %}<\/tr>
        {% endfor %}<\/tbody>
      <\/table>
    <\/div>
    <div class="flex gap-3"><button type="submit" class="btn btn-navy">{% if obj %}Save changes{% else %}Create invoice{% endif %}<\/button><a href="{% url 'invoices:list' %}" class="btn btn-outline">Cancel<\/a><\/div>
  <\/form>
<\/div>
{% endblock %}
"""
w("templates/invoices/form.html", INV_FORM)

REPORTS_HTML = """
{% extends 'base.html' %}
{% block title %}Reports - FinanceHub{% endblock %}
{% block nav_reports %}active{% endblock %}
{% block page_title %}Financial Reports{% endblock %}
{% block page_sub %}Summary for {{ year }}{% endblock %}
{% block header_actions %}<form method="get" class="flex items-center gap-2"><select name="year" class="form-input w-32" onchange="this.form.submit()">{% for y in years %}<option value="{{ y }}" {% if y == year %}selected{% endif %}>{{ y }}<\/option>{% endfor %}<\/select><\/form>{% endblock %}
{% block content %}
<div class="space-y-5">
  <div class="grid grid-cols-3 gap-4">
    <div class="card border-l-4" style="border-color:#16a34a"><p class="text-slate-400 text-xs uppercase tracking-wide font-medium">Total Income {{ year }}<\/p><p class="text-2xl font-bold mt-1 text-green-600">${{ total_income|floatformat:2 }}<\/p><\/div>
    <div class="card border-l-4" style="border-color:#dc2626"><p class="text-slate-400 text-xs uppercase tracking-wide font-medium">Total Expenses {{ year }}<\/p><p class="text-2xl font-bold mt-1 text-red-500">${{ total_expense|floatformat:2 }}<\/p><\/div>
    <div class="card border-l-4" style="border-color:#c9a84c"><p class="text-slate-400 text-xs uppercase tracking-wide font-medium">Net Profit {{ year }}<\/p><p class="text-2xl font-bold mt-1 {% if net >= 0 %}text-slate-800{% else %}text-red-600{% endif %}">${{ net|floatformat:2 }}<\/p><\/div>
  <\/div>
  <div class="card"><h3 class="font-semibold text-slate-700 text-sm mb-4">Monthly Income vs Expenses<\/h3><canvas id="monthlyChart" height="120"><\/canvas><\/div>
  <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
    <div class="card"><h3 class="font-semibold text-slate-700 text-sm mb-4">Expense by Category<\/h3><canvas id="catChart" height="220"><\/canvas><\/div>
    <div class="card"><h3 class="font-semibold text-slate-700 text-sm mb-4">Category Details<\/h3><div id="cat-list"><p class="text-slate-400 text-sm">Loading...<\/p><\/div><\/div>
  <\/div>
<\/div>
{% endblock %}
{% block scripts %}
<script>
var monthly = {{ monthly_data|safe }};
var catData  = {{ category_data|safe }};

new Chart(document.getElementById('monthlyChart'), {
  type: 'bar',
  data: {
    labels: monthly.map(function(d){return d.label;}),
    datasets: [
      {label:'Income', data:monthly.map(function(d){return d.income;}), backgroundColor:'rgba(22,163,74,.2)', borderColor:'#16a34a', borderWidth:2, borderRadius:4},
      {label:'Expense',data:monthly.map(function(d){return d.expense;}),backgroundColor:'rgba(220,38,38,.15)',borderColor:'#dc2626',borderWidth:2,borderRadius:4}
    ]
  },
  options:{responsive:true,scales:{x:{grid:{display:false}},y:{grid:{color:'#f1f5f9'},ticks:{callback:function(v){return '$'+v;}}}}}
});

if (catData.length) {
  new Chart(document.getElementById('catChart'), {
    type: 'doughnut',
    data: {labels:catData.map(function(c){return c.name;}),datasets:[{data:catData.map(function(c){return c.total;}),backgroundColor:catData.map(function(c){return c.color;}),borderWidth:2,borderColor:'#fff'}]},
    options:{responsive:true,plugins:{legend:{position:'bottom',labels:{font:{size:11},boxWidth:12}}}}
  });
  var html = catData.map(function(c){return '<div class="flex justify-between items-center py-1.5 border-b border-slate-50 last:border-0"><div class="flex items-center gap-2"><div class="w-3 h-3 rounded-full" style="background:'+c.color+'"><\/div><span class="text-slate-700 text-sm">'+c.name+'<\/span><\/div><span class="font-semibold text-slate-800 text-sm">$'+c.total.toFixed(2)+'<\/span><\/div>';}).join('');
  document.getElementById('cat-list').innerHTML = html;
} else {
  document.getElementById('cat-list').innerHTML = '<p class="text-slate-400 text-sm">No expense data for this year.<\/p>';
}
<\/script>
{% endblock %}
"""
w("templates/reports/index.html", REPORTS_HTML)

print("\n  All templates written!\n")
print("="*52)
print("  NEXT STEPS:")
print("  1. Edit .env  -  set your MySQL password")
print("  2. pip install -r requirements.txt")
print("  3. python manage.py makemigrations accounts finance projects clients invoices dashboard reports")
print("  4. python manage.py migrate")
print("  5. python manage.py createsuperuser")
print("  6. python manage.py runserver")
print("  7. http://127.0.0.1:8000/")
print("="*52)
