using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace Assets.Scripts
{
	[ExecuteInEditMode]
	public class TSGMesh : MonoBehaviour
	{
		public bool SwapUV;

		private MeshFilter _filter;

		void Start()
			=> _filter = GetComponent<MeshFilter>();

		void OnValidate()
		{
			if (SwapUV)
			{
				SwapUVs();
			}
			SwapUV = false;
		}

		private void SwapUVs()
		{
			var uv1 = _filter.sharedMesh.uv;
			var uv2 = _filter.sharedMesh.uv2;
			_filter.sharedMesh.uv = uv2;
			_filter.sharedMesh.uv2 = uv1;
			Debug.Log($"uv is now {_filter.sharedMesh.uv}, uv2 is now {_filter.sharedMesh.uv2}");
		}
	}
}
