from supabase import create_client, Client

url = "https://nqclochtpzaogvzazmnm.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5xY2xvY2h0cHphb2d2emF6bW5tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDU1NTY5MzMsImV4cCI6MjA2MTEzMjkzM30.ZZk7Hr9YtBO7J4q6bUwMCQi1yB-E5oW6-ZGM1EYaC5M"
supabase: Client = create_client(url, key)
