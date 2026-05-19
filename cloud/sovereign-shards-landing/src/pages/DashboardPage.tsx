import { useQuery, useMutation } from "convex/react";
import { api } from "../../convex/_generated/api";
import type { Id } from "../../convex/_generated/dataModel";

export function DashboardPage() {
  const preorders = useQuery(api.preorders.list);
  const count = useQuery(api.preorders.count);
  const updateStatus = useMutation(api.preorders.updateStatus);

  const totalRevenue = preorders?.reduce((sum, p) => sum + p.amount, 0) ?? 0;
  const pending = preorders?.filter((p) => p.status === "pending").length ?? 0;
  const confirmed = preorders?.filter((p) => p.status === "confirmed").length ?? 0;

  const handleStatus = async (id: Id<"preorders">, status: string) => {
    await updateStatus({ id, status });
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Pre-Order Dashboard</h1>
        <p className="text-muted-foreground">Manage Sovereign Shards pre-orders</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Orders", value: count ?? 0, color: "text-blue-500" },
          { label: "Pending", value: pending, color: "text-yellow-500" },
          { label: "Confirmed", value: confirmed, color: "text-green-500" },
          { label: "Revenue (Reserved)", value: `$${(totalRevenue / 100).toFixed(2)}`, color: "text-emerald-500" },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border bg-card p-4">
            <p className="text-sm text-muted-foreground">{s.label}</p>
            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {/* Orders table */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="text-left p-3 font-medium">Name</th>
                <th className="text-left p-3 font-medium">Email</th>
                <th className="text-left p-3 font-medium">Tier</th>
                <th className="text-left p-3 font-medium">Amount</th>
                <th className="text-left p-3 font-medium">Status</th>
                <th className="text-left p-3 font-medium">Date</th>
                <th className="text-left p-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {preorders?.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-muted-foreground">
                    No pre-orders yet. Share the landing page to start collecting orders.
                  </td>
                </tr>
              )}
              {preorders?.map((order) => (
                <tr key={order._id} className="border-b last:border-0">
                  <td className="p-3 font-medium">{order.name}</td>
                  <td className="p-3 text-muted-foreground">{order.email}</td>
                  <td className="p-3">
                    <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-blue-500/10 text-blue-500">
                      {order.tier}
                    </span>
                  </td>
                  <td className="p-3">${(order.amount / 100).toFixed(2)}</td>
                  <td className="p-3">
                    <span
                      className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        order.status === "confirmed"
                          ? "bg-green-500/10 text-green-500"
                          : order.status === "cancelled"
                            ? "bg-red-500/10 text-red-500"
                            : "bg-yellow-500/10 text-yellow-500"
                      }`}
                    >
                      {order.status}
                    </span>
                  </td>
                  <td className="p-3 text-muted-foreground text-xs">
                    {new Date(order.createdAt).toLocaleDateString()}
                  </td>
                  <td className="p-3">
                    <div className="flex gap-1">
                      {order.status !== "confirmed" && (
                        <button
                          type="button"
                          onClick={() => handleStatus(order._id, "confirmed")}
                          className="px-2 py-1 text-xs bg-green-500/10 text-green-500 rounded hover:bg-green-500/20 transition"
                        >
                          Confirm
                        </button>
                      )}
                      {order.status !== "cancelled" && (
                        <button
                          type="button"
                          onClick={() => handleStatus(order._id, "cancelled")}
                          className="px-2 py-1 text-xs bg-red-500/10 text-red-500 rounded hover:bg-red-500/20 transition"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
