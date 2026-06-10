import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

df = pd.read_csv("weibo_comments_all_predicted_cleaned.csv", encoding="utf-8-sig")

print("=== 修正后 support_zhang Top 5 ===")
sub = df[df["predicted_stance"] == "support_zhang"].sort_values("like_count", ascending=False)
for i, (_, r) in enumerate(sub.head(5).iterrows()):
    print("{}. [点赞 {}] {}".format(i+1, int(r["like_count"]), r["comment_text"][:80]))

print("\n=== 修正后 support_wang Top 5 ===")
sub = df[df["predicted_stance"] == "support_wang"].sort_values("like_count", ascending=False)
for i, (_, r) in enumerate(sub.head(5).iterrows()):
    print("{}. [点赞 {}] {}".format(i+1, int(r["like_count"]), r["comment_text"][:80]))
