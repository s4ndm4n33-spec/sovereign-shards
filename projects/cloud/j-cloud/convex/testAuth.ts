import { ConvexCredentials } from "@convex-dev/auth/providers/ConvexCredentials";
import { createAccount, retrieveAccount } from "@convex-dev/auth/server";
import { Scrypt } from "lucia";
import type { DataModel } from "./_generated/dataModel";

const TEST_EMAIL_DOMAIN = "test.local";

function isTestEmail(email: string): boolean {
  return email.endsWith(`@${TEST_EMAIL_DOMAIN}`);
}

export const TestCredentials = ConvexCredentials<DataModel>({
  id: "test",
  crypto: {
    async hashSecret(password: string) {
      return await new Scrypt().hash(password);
    },
    async verifySecret(password: string, hash: string) {
      return await new Scrypt().verify(hash, password);
    },
  },
  authorize: async (params, ctx) => {
    const email = params.email as string;
    const password = params.password as string;
    const flow = params.flow as string;

    if (!email || !isTestEmail(email)) {
      throw new Error("Only @test.local emails allowed for test auth");
    }

    if (!password || password.length < 6) {
      throw new Error("Password must be at least 6 characters");
    }

    if (flow === "signUp") {
      try {
        const existing = await retrieveAccount(ctx, {
          provider: "test",
          account: {
            id: email,
            secret: password,
          },
        });
        return { userId: existing.user._id };
      } catch {
        // Account doesn't exist or password doesn't match, create new
      }

      const { user } = await createAccount(ctx, {
        provider: "test",
        account: {
          id: email,
          secret: password,
        },
        profile: {
          email,
          name: (params.name as string) || "Test User",
          emailVerificationTime: Date.now(),
        },
        shouldLinkViaEmail: false,
      });

      return { userId: user._id };
    }

    const result = await retrieveAccount(ctx, {
      provider: "test",
      account: {
        id: email,
        secret: password,
      },
    });

    return { userId: result.user._id };
  },
});
