export interface CurrentUser {
  name: string;
  email: string;
}

export interface UserConfigChoiceOption {
  value: string;
  label: string;
}

export interface UserConfigItem {
  key: string;
  name: string;
  config_type: 'boolean' | 'choice';
  description: string;
  options: UserConfigChoiceOption[];
  value: boolean | string;
  default_value: boolean | string;
  using_default: boolean;
}

export interface LoginRequest {
  email: string;
  password: string;
  session_mode: 'web';
  issuance_policy: 'session';
}
