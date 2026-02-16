public class Guid32
{
	public const uint INVALID_VALUE = 0xBADBADBA;

	public uint Value { get; private set; }

	public Guid32()
	{
		Invalidate();
	}

	public Guid32(uint val)
	{
		Value = val;
	}

	public void Clear()
	{
		Value = 0;
	}

	public void Invalidate()
	{
		Value = INVALID_VALUE;
	}

	public bool IsClear() => Value == 0;
	public bool IsValid() => Value != INVALID_VALUE;

	public override string ToString()
	{
		if (SDBMHash.PrecomputedHashes.TryGetValue(Value, out var list))
		{
			if (list.Count == 1)
			{
				return $"{Value:X8} ({list[0]})";
			}

			var str = $"{Value:X8} (";
			foreach (var item in list)
			{
				str += $"{item}, ";
			}

			return str + ")";
		}

		return $"{Value:X8}";
	}
}