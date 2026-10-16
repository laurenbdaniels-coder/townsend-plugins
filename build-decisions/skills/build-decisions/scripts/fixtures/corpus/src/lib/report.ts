export const send = (total: number) => fetch(`${process.env.API || 'http://localhost:3000'}/charge`, { body: String(Math.round(total * 100)) });
