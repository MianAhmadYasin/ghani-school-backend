# ✅ Railway Deployment Checklist

Use this checklist to ensure a smooth deployment to Railway.

---

## 📋 Pre-Deployment

### Supabase Setup
- [ ] Supabase project created
- [ ] Database tables created (run all SQL migration files)
- [ ] Supabase URL copied
- [ ] Supabase anon key copied
- [ ] Supabase service role key copied (keep secret!)

### Environment Variables
- [ ] JWT secret key generated (32+ characters)
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- [ ] Frontend URL determined (for CORS)

### Code Preparation
- [ ] Code pushed to GitHub
- [ ] All tests passing (if applicable)
- [ ] `.env` file NOT committed (should be in `.gitignore`)

---

## 🚂 Railway Deployment

### Project Setup
- [ ] Railway account created
- [ ] New project created in Railway
- [ ] GitHub repository connected
- [ ] Root directory set to `backend`

### Environment Variables in Railway
- [ ] `SUPABASE_URL` set
- [ ] `SUPABASE_KEY` set
- [ ] `SUPABASE_SERVICE_KEY` set
- [ ] `JWT_SECRET_KEY` set (32+ characters)
- [ ] `FRONTEND_URL` set
- [ ] `DEBUG` set to `false`
- [ ] `ENVIRONMENT` set to `production`

### Deployment
- [ ] Build completed successfully
- [ ] Deployment successful
- [ ] No errors in logs

---

## ✅ Post-Deployment Verification

### Health Check
- [ ] Health endpoint accessible: `GET /health`
- [ ] Returns `{"status": "healthy", "database": "connected"}`
- [ ] Status code is 200

### API Testing
- [ ] Root endpoint works: `GET /`
- [ ] API docs accessible (if DEBUG=true): `GET /api/docs`
- [ ] Authentication endpoint works: `POST /api/v1/auth/login`

### Logs
- [ ] No error messages in Railway logs
- [ ] See: `✅ Configuration validated successfully`
- [ ] See: `Starting School Management System v1.0.0`
- [ ] Database connection successful

### CORS
- [ ] Frontend can make API requests
- [ ] No CORS errors in browser console
- [ ] `FRONTEND_URL` matches frontend domain exactly

---

## 🔧 Configuration

### Backend URL
- [ ] Railway domain copied
- [ ] Custom domain configured (optional)
- [ ] Frontend environment variables updated with backend URL

### Monitoring
- [ ] Railway metrics dashboard accessible
- [ ] Logs streaming correctly
- [ ] Health check monitoring set up (optional)

---

## 🎯 Final Steps

- [ ] Frontend deployed and connected to backend
- [ ] Test user login works
- [ ] Test creating a student/teacher (if admin)
- [ ] All major features tested
- [ ] Documentation updated with production URLs

---

## 🐛 Common Issues

If deployment fails, check:

1. **Build fails**: Check `requirements.txt` and `Dockerfile`
2. **App crashes**: Verify all environment variables are set
3. **Database errors**: Check Supabase credentials and table creation
4. **CORS errors**: Verify `FRONTEND_URL` matches exactly
5. **Port errors**: Railway sets PORT automatically - don't override it

---

## 📞 Support Resources

- **Railway Docs**: [docs.railway.app](https://docs.railway.app)
- **Full Deployment Guide**: `RAILWAY_DEPLOYMENT_GUIDE.md`
- **Quick Deploy Guide**: `RAILWAY_QUICK_DEPLOY.md`

---

**✅ All checked? Your backend is production-ready! 🎉**

