class ReportPolicy
  def show?
    if user.admin?
      true
    end
  end
end
