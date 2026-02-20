export interface CurrentUser {
  name: string;
  email: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  session_mode: 'web';
  issuance_policy: 'session';
}
