# 🚂 Railway Quick Deploy Guide

**Deploy your backend in 5 minutes!**

---

## ✅ Pre-Deployment Checklist

Before deploying, make sure you have:

- [ ] Railway account ([railway.app](https://railway.app))
- [ ] Supabase project with database tables created
- [ ] Supabase API keys (URL, anon key, service role key)
- [ ] JWT secret key (32+ characters)

---

## 🚀 Step 1: Get Your Supabase Keys

1. Go to [app.supabase.com](https://app.supabase.com)
2. Select your project → **Settings** → **API**
3. Copy these values:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** key → `SUPABASE_KEY`
   - **service_role** key → `SUPABASE_SERVICE_KEY` ⚠️ Keep secret!

---

## 🔑 Step 2: Generate JWT Secret

Run this command to generate a secure JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output - you'll need it for `JWT_SECRET_KEY`.

---

## 🚂 Step 3: Deploy to Railway

### Option A: Via Railway Dashboard (Easiest)

1. **Go to Railway**: [railway.app](https://railway.app)
2. **New Project** → **Deploy from GitHub repo**
3. **Select your repository**
4. **Set Root Directory**: Click on the service → **Settings** → **Root Directory** → Set to `backend`
5. **Add Environment Variables**: Go to **Variables** tab and add:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
SUPABASE_SERVICE_KEY=your-service-role-key-here
JWT_SECRET_KEY=your-generated-secret-key-here
FRONTEND_URL=https://your-frontend-domain.com
DEBUG=false
ENVIRONMENT=production
```

6. **Deploy**: Railway will automatically build and deploy!

### Option B: Via Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Navigate to backend
cd backend

# Initialize Railway project
railway init

# Set environment variables
railway variables set SUPABASE_URL=https://your-project.supabase.co
railway variables set SUPABASE_KEY=your-anon-key
railway variables set SUPABASE_SERVICE_KEY=your-service-role-key
railway variables set JWT_SECRET_KEY=your-secret-key
railway variables set FRONTEND_URL=https://your-frontend-domain.com
railway variables set DEBUG=false
railway variables set ENVIRONMENT=production

# Deploy
railway up
```

---

## ✅ Step 4: Verify Deployment

1. **Get your backend URL**: Railway dashboard → **Settings** → **Domains**
2. **Test health endpoint**:
   ```bash
   curl https://your-backend.railway.app/health
   ```
   Should return:
   ```json
   {
     "status": "healthy",
     "service": "School Management System",
     "version": "1.0.0",
     "database": "connected"
   }
   ```

3. **Check logs**: Railway dashboard → **Deployments** → Latest → **View Logs**
   - Look for: `✅ Configuration validated successfully`
   - Look for: `Starting School Management System v1.0.0`

---

## 🔧 Step 5: Update Frontend

After deployment, update your frontend environment variables:

```env
NEXT_PUBLIC_API_URL=https://your-backend.railway.app/api/v1
```

---

## 🐛 Troubleshooting

### Build Fails
- Check Railway logs for errors
- Verify `requirements.txt` is correct
- Ensure `Dockerfile` exists in `backend/` directory

### App Crashes on Startup
- ✅ All environment variables set?
- ✅ Supabase credentials correct?
- ✅ JWT_SECRET_KEY is 32+ characters?
- ✅ Database tables created in Supabase?

### Database Connection Fails
- ✅ `SUPABASE_URL` is correct?
- ✅ `SUPABASE_SERVICE_KEY` is the service role key (not anon key)?
- ✅ Supabase project is active?

### CORS Errors
- Update `FRONTEND_URL` in Railway variables
- Restart service after updating env vars

---

## 📊 Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | ✅ Yes | Your Supabase project URL |
| `SUPABASE_KEY` | ✅ Yes | Supabase anon/public key |
| `SUPABASE_SERVICE_KEY` | ✅ Yes | Supabase service role key |
| `JWT_SECRET_KEY` | ✅ Yes | JWT secret (min 32 chars) |
| `FRONTEND_URL` | ✅ Yes | Your frontend URL |
| `DEBUG` | No | Set to `false` in production |
| `ENVIRONMENT` | No | Set to `production` |
| `PORT` | Auto | Railway sets this automatically |

---

## 🎉 You're Done!

Your backend is now live on Railway! 

**Next Steps:**
1. Deploy frontend to Vercel/Netlify
2. Update `FRONTEND_URL` in Railway
3. Test all API endpoints
4. Set up monitoring

---

**Need Help?** Check the full guide: `RAILWAY_DEPLOYMENT_GUIDE.md`

