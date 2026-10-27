export type StatusMessage =
  | "success"
  | "created"
  | "deleted"
  | "updated"
  | "found"
  | "not found"
  | "approved";

export type ApiResponse<T> = {
  status_message: StatusMessage;
  data: T;
};
