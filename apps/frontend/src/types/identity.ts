export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
  active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
