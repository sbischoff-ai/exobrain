<script>
  import ChatView from '$lib/components/ChatView.svelte';
  import UserMenu from '$lib/components/UserMenu.svelte';
</script>

<svelte:head>
  <title>Exobrain Assistant</title>
</svelte:head>

<div class="app-shell">
  <header class="header">
    <div class="header-inner">
      <div class="brand">
        <img src="/logo.png" alt="Exobrain logo" class="logo" />
        <h1>EXOBRAIN</h1>
      </div>
      <UserMenu />
    </div>
  </header>

  <main class="main-content">
    <ChatView />
  </main>
</div>
