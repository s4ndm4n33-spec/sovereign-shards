import { Email } from "@convex-dev/auth/providers/Email";
import { APP_NAME } from "./constants";

declare const process: { env: Record<string, string | undefined> };

function generateOTP() {
  const array = new Uint32Array(1);
  crypto.getRandomValues(array);
  return String(array[0] % 1000000).padStart(6, "0");
}

async function sendEmail({
  email,
  token,
  subject,
  heading,
  description,
}: {
  email: string;
  token: string;
  subject: string;
  heading: string;
  description: string;
}) {
  const apiUrl = process.env.VIKTOR_SPACES_API_URL;
  const projectName = process.env.VIKTOR_SPACES_PROJECT_NAME;
  const projectSecret = process.env.VIKTOR_SPACES_PROJECT_SECRET;

  if (!apiUrl || !projectName || !projectSecret) {
    throw new Error(
      "Viktor Spaces environment variables not configured. " +
        "Required: VIKTOR_SPACES_API_URL, VIKTOR_SPACES_PROJECT_NAME, VIKTOR_SPACES_PROJECT_SECRET",
    );
  }

  const response = await fetch(`${apiUrl}/api/viktor-spaces/send-email`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      project_name: projectName,
      project_secret: projectSecret,
      to_email: email,
      subject: `${subject} - ${APP_NAME}`,
      html_content: `
        <div style="font-family: sans-serif; max-width: 400px; margin: 0 auto; padding: 20px;">
          <h2 style="color: #333;">${heading}</h2>
          <p style="color: #666;">${description}</p>
          <div style="background: #f5f5f5; padding: 20px; text-align: center; border-radius: 8px; margin: 20px 0;">
            <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #333;">${token}</span>
          </div>
          <p style="color: #999; font-size: 12px;">This code expires in 15 minutes.</p>
          <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" />
          <p style="color: #999; font-size: 12px; text-align: center;">This email was sent by ${APP_NAME}</p>
        </div>
      `,
      text_content: `${heading}\n\n${description}\n\nYour code is: ${token}\n\nThis code expires in 15 minutes.\n\n---\nThis email was sent by ${APP_NAME}`,
      email_type: "otp",
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to send email: ${error}`);
  }

  const result = (await response.json()) as {
    success: boolean;
    error?: string;
  };
  if (!result.success) {
    throw new Error(`Email sending failed: ${result.error}`);
  }
}

/**
 * Email verification provider for sign-up flow.
 * Sends OTP codes via Viktor Spaces API which:
 * - Rate limits per project (100 emails/hour)
 * - Sends from project-specific email addresses
 * - Keeps the Resend API key secure on the backend
 */
export const ViktorSpacesEmail = Email({
  id: "viktor-spaces-email",
  maxAge: 60 * 15, // 15 minutes

  async generateVerificationToken() {
    return generateOTP();
  },

  async sendVerificationRequest({ identifier: email, token }) {
    await sendEmail({
      email,
      token,
      subject: "Verify your email",
      heading: "Verify your email",
      description: "Your verification code is:",
    });
  },
});

/**
 * Password reset email provider.
 * Uses the same Viktor Spaces API but with different email template.
 */
export const ViktorSpacesPasswordReset = Email({
  id: "viktor-spaces-password-reset",
  maxAge: 60 * 15, // 15 minutes

  async generateVerificationToken() {
    return generateOTP();
  },

  async sendVerificationRequest({ identifier: email, token }) {
    await sendEmail({
      email,
      token,
      subject: "Reset your password",
      heading: "Reset your password",
      description: "Your password reset code is:",
    });
  },
});
