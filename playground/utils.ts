type User = {
  id: number;
  name: string;
  email: string;
  role: "admin" | "editor" | "viewer";
};

type Post = {
  id: number;
  title: string;
  body: string;
  authorId: number;
  publishedAt: Date | null;
};

export function filterByRole(users: User[], role: User["role"]): User[] {
  return users.filter((u) => u.role === role);
}

export function publishPost(post: Post): Post {
  if (post.publishedAt !== null) {
    throw new Error(`Post ${post.id} is already published`);
  }
  return { ...post, publishedAt: new Date() };
}

export function getAuthor(users: User[], post: Post): User | undefined {
  return users.find((u) => u.id === post.authorId);
}

export function summarize(posts: Post[]): { total: number; published: number; drafts: number } {
  const published = posts.filter((p) => p.publishedAt !== null).length;
  return { total: posts.length, published, drafts: posts.length - published };
}
