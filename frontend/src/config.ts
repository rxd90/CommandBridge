export const config = {
  cognitoRegion: import.meta.env.VITE_COGNITO_REGION || 'eu-west-2',
  cognitoUserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || 'eu-west-2_quMz1HdKl',
  cognitoClientId: import.meta.env.VITE_COGNITO_CLIENT_ID || '5a51q77lgugmpan0t3qpq2spt4',
  cognitoDomain: import.meta.env.VITE_COGNITO_DOMAIN || 'commandbridge-dev.auth.eu-west-2.amazoncognito.com',
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL || 'https://p4afq4i3i4.execute-api.eu-west-2.amazonaws.com',
  redirectUri: import.meta.env.VITE_REDIRECT_URI || 'https://d2ej3zpo2eta45.cloudfront.net/callback',
  logoutUri: import.meta.env.VITE_LOGOUT_URI || 'https://d2ej3zpo2eta45.cloudfront.net/login',
  localDev: import.meta.env.VITE_LOCAL_DEV === 'true',
} as const;
