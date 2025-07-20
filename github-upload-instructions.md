# GitHub Upload Instructions

## Essential Files for Vercel Deployment:

### 1. Create these files in GitHub web interface:

**package.json** (in root):
```json
{
  "name": "petromatch-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.0.3",
    "react": "^18",
    "react-dom": "^18",
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "typescript": "^5",
    "tailwindcss": "^3.3.0",
    "autoprefixer": "^10.0.1",
    "postcss": "^8",
    "axios": "^1.6.0",
    "js-cookie": "^3.0.5",
    "react-hook-form": "^7.47.0",
    "react-hot-toast": "^2.4.1",
    "lucide-react": "^0.294.0"
  }
}
```

**vercel.json** (in root):
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "env": {
    "NEXT_PUBLIC_API_URL": "https://shinkansen.proxy.rlwy.net"
  }
}
```

## OR: Alternative - Use GitHub CLI
If you have `gh` CLI:
```bash
gh repo create petromatch --public
gh repo push
```