export type StatusMessage =
  | "success"
  | "created"
  | "deleted"
  | "updated"
  | "found"
  | "not found"
  | "approved"
  | "continued";

export type ApiResponse<T> = {
  status_message: StatusMessage;
  data: T;
};
